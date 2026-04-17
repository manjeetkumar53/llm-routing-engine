"""
LLM Routing Engine — Analytics Dashboard

Run:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────
DB_PATH = Path("telemetry.db")
BENCHMARK_RESULTS = Path("benchmark/results.json")

st.set_page_config(
    page_title="LLM Routing Engine",
    page_icon="⚡",
    layout="wide",
)

# ── Data loading ───────────────────────────────────────────────────────────

@st.cache_data(ttl=5)
def load_events() -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM events ORDER BY created_at DESC LIMIT 500").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=60)
def load_benchmark() -> dict | None:
    if not BENCHMARK_RESULTS.exists():
        return None
    with open(BENCHMARK_RESULTS) as f:
        return json.load(f)


# ── Header ─────────────────────────────────────────────────────────────────
st.title("⚡ LLM Routing Engine — Analytics")
st.caption("Live telemetry · Experiment comparison · Cost analysis")

events = load_events()
benchmark = load_benchmark()

if not events:
    st.warning("No telemetry data yet. Send requests to `/v1/route/infer` to populate.")
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────
total = len(events)
cheap_count = sum(1 for e in events if e["selected_tier"] == "cheap")
premium_count = total - cheap_count
avg_cost = sum(e["estimated_cost_usd"] for e in events) / total
avg_latency = sum(e["latency_ms"] for e in events) / total

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Requests", total)
k2.metric("Cheap / Premium", f"{cheap_count} / {premium_count}")
k3.metric("Avg Cost / Req", f"${avg_cost:.6f}")
k4.metric("Avg Latency", f"{avg_latency:.1f} ms")

st.divider()

# ── Chart 1: Requests by tier ──────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Requests by Tier")
    tier_data = {"Tier": ["cheap", "premium"], "Count": [cheap_count, premium_count]}
    fig = px.pie(
        tier_data,
        names="Tier",
        values="Count",
        color="Tier",
        color_discrete_map={"cheap": "#36b37e", "premium": "#ff5630"},
        hole=0.4,
    )
    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

# ── Chart 2: Cost per request over time ───────────────────────────────────
with col2:
    st.subheader("Cost per Request (recent 100)")
    recent = events[:100][::-1]
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=list(range(len(recent))),
            y=[e["estimated_cost_usd"] for e in recent],
            mode="lines+markers",
            marker=dict(
                color=["#36b37e" if e["selected_tier"] == "cheap" else "#ff5630" for e in recent],
                size=6,
            ),
            line=dict(color="#6554c0", width=1),
            name="cost",
        )
    )
    fig2.update_layout(
        xaxis_title="Request #",
        yaxis_title="Cost (USD)",
        margin=dict(t=10, b=30, l=40, r=10),
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── Chart 3: Latency distribution ─────────────────────────────────────────
col3, col4 = st.columns(2)

with col3:
    st.subheader("Latency Distribution (ms)")
    latencies = [e["latency_ms"] for e in events]
    fig3 = px.histogram(
        x=latencies,
        nbins=30,
        labels={"x": "Latency (ms)", "y": "Requests"},
        color_discrete_sequence=["#6554c0"],
    )
    fig3.update_layout(margin=dict(t=10, b=30, l=40, r=10))
    st.plotly_chart(fig3, use_container_width=True)

# ── Chart 4: Requests by experiment mode ──────────────────────────────────
with col4:
    st.subheader("Requests by Experiment Mode")
    mode_counts: dict[str, int] = {}
    for e in events:
        mode_counts[e["experiment_mode"]] = mode_counts.get(e["experiment_mode"], 0) + 1

    fig4 = px.bar(
        x=list(mode_counts.keys()),
        y=list(mode_counts.values()),
        labels={"x": "Mode", "y": "Requests"},
        color=list(mode_counts.keys()),
        color_discrete_sequence=["#0052cc", "#36b37e", "#ff5630"],
    )
    fig4.update_layout(
        margin=dict(t=10, b=30, l=40, r=10),
        showlegend=False,
    )
    st.plotly_chart(fig4, use_container_width=True)

# ── Benchmark comparison ───────────────────────────────────────────────────
if benchmark:
    st.divider()
    st.subheader("Benchmark: Router vs Baselines")

    comp = benchmark["comparison"]
    b1, b2, b3 = st.columns(3)
    b1.metric(
        "Cost Savings vs Always-Premium",
        f"{comp['router_vs_premium_cost_savings_pct']}%",
        delta=f"-{comp['router_vs_premium_cost_savings_pct']}% cost",
        delta_color="inverse",
    )
    b2.metric("Router Routing Accuracy", f"{comp['router_routing_accuracy_pct']}%")
    b3.metric(
        "Premium Baseline Cost",
        f"${comp['premium_baseline_cost_usd']:.6f}",
        delta=f"Router: ${comp['router_cost_usd']:.6f}",
        delta_color="inverse",
    )

    summaries = benchmark["summaries"]
    modes = [s["mode"] for s in summaries]
    costs = [s["total_cost_usd"] for s in summaries]
    accuracies = [s["routing_accuracy_pct"] for s in summaries]

    bc1, bc2 = st.columns(2)
    with bc1:
        fig5 = px.bar(
            x=modes,
            y=costs,
            labels={"x": "Mode", "y": "Total Cost (USD)"},
            title="Total Cost by Mode (50 prompts)",
            color=modes,
            color_discrete_sequence=["#0052cc", "#36b37e", "#ff5630"],
        )
        fig5.update_layout(showlegend=False, margin=dict(t=40, b=30))
        st.plotly_chart(fig5, use_container_width=True)

    with bc2:
        fig6 = px.bar(
            x=modes,
            y=accuracies,
            labels={"x": "Mode", "y": "Routing Accuracy (%)"},
            title="Routing Accuracy by Mode",
            color=modes,
            color_discrete_sequence=["#0052cc", "#36b37e", "#ff5630"],
        )
        fig6.update_layout(showlegend=False, margin=dict(t=40, b=30), yaxis_range=[0, 100])
        st.plotly_chart(fig6, use_container_width=True)

# ── Raw events ─────────────────────────────────────────────────────────────
st.divider()
with st.expander("Raw Telemetry Events (last 50)"):
    st.dataframe(events[:50], use_container_width=True)
