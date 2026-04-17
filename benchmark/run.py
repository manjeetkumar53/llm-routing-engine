"""
Benchmark runner: compares three experiment modes across the 50-prompt dataset.

Usage:
    python -m benchmark.run
    python -m benchmark.run --prompts benchmark/prompts.json --output benchmark/results.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from app.config import load_settings
from app.experiment import ExperimentMode
from app.providers.mock_provider import MockLLMProvider
from app.router import RoutingEngine
from app.services.telemetry import TelemetryStore


def _run_mode(
    engine: RoutingEngine,
    prompts: list[dict],
    mode: ExperimentMode,
) -> list[dict]:
    results = []
    for item in prompts:
        t0 = time.perf_counter()
        resp = engine.infer(item["prompt"], mode=mode)
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        results.append(
            {
                "id": item["id"],
                "mode": mode.value,
                "expected_tier": item["expected_tier"],
                "selected_tier": resp.route.selected_tier,
                "complexity_score": resp.route.complexity_score,
                "correct_routing": resp.route.selected_tier == item["expected_tier"],
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "estimated_cost_usd": resp.estimated_cost_usd,
                "latency_ms": elapsed,
                "fallback_used": resp.fallback_used,
            }
        )
    return results


def _percentile(data: list[float], p: int) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(sorted_data) - 1)
    return round(sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * (k - lo), 2)


def _summarize(results: list[dict], mode: str) -> dict:
    subset = [r for r in results if r["mode"] == mode]
    latencies = [r["latency_ms"] for r in subset]
    costs = [r["estimated_cost_usd"] for r in subset]
    correct = sum(1 for r in subset if r["correct_routing"])
    cheap_count = sum(1 for r in subset if r["selected_tier"] == "cheap")
    premium_count = sum(1 for r in subset if r["selected_tier"] == "premium")
    total = len(subset)
    return {
        "mode": mode,
        "total_prompts": total,
        "routing_accuracy_pct": round(correct / total * 100, 1) if total else 0,
        "cheap_count": cheap_count,
        "premium_count": premium_count,
        "total_cost_usd": round(sum(costs), 6),
        "avg_cost_usd": round(statistics.mean(costs), 8) if costs else 0,
        "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
        "p95_latency_ms": _percentile(latencies, 95),
        "fallback_count": sum(1 for r in subset if r["fallback_used"]),
    }


def main(prompts_path: Path, output_path: Path | None) -> None:
    with open(prompts_path) as f:
        prompts = json.load(f)

    settings = load_settings()
    provider = MockLLMProvider()

    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        telemetry = TelemetryStore(db_path=Path(tmp.name))
        engine = RoutingEngine(settings=settings, provider=provider, telemetry=telemetry)

        all_results: list[dict] = []
        for mode in ExperimentMode:
            print(f"  Running mode: {mode.value} ({len(prompts)} prompts)...")
            all_results.extend(_run_mode(engine, prompts, mode))

    summaries = [_summarize(all_results, m.value) for m in ExperimentMode]
    router_summary = next(s for s in summaries if s["mode"] == "router_v1")
    premium_summary = next(s for s in summaries if s["mode"] == "always_premium")

    cost_savings_pct = round(
        (1 - router_summary["total_cost_usd"] / premium_summary["total_cost_usd"]) * 100, 1
    ) if premium_summary["total_cost_usd"] > 0 else 0

    report = {
        "summaries": summaries,
        "comparison": {
            "router_vs_premium_cost_savings_pct": cost_savings_pct,
            "router_routing_accuracy_pct": router_summary["routing_accuracy_pct"],
            "premium_baseline_cost_usd": premium_summary["total_cost_usd"],
            "router_cost_usd": router_summary["total_cost_usd"],
        },
    }

    _print_report(report)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull results written to {output_path}")


def _print_report(report: dict) -> None:
    print("\n" + "=" * 60)
    print("  BENCHMARK REPORT")
    print("=" * 60)
    for s in report["summaries"]:
        print(f"\n[{s['mode']}]")
        print(f"  Routing accuracy : {s['routing_accuracy_pct']}%")
        print(f"  Cheap / Premium  : {s['cheap_count']} / {s['premium_count']}")
        print(f"  Total cost (USD) : ${s['total_cost_usd']:.6f}")
        print(f"  Avg latency (ms) : {s['avg_latency_ms']}")
        print(f"  p95 latency (ms) : {s['p95_latency_ms']}")
        print(f"  Fallbacks        : {s['fallback_count']}")

    c = report["comparison"]
    print("\n" + "-" * 60)
    print("  ROUTER vs ALWAYS_PREMIUM")
    print(f"  Cost savings      : {c['router_vs_premium_cost_savings_pct']}%")
    print(f"  Routing accuracy  : {c['router_routing_accuracy_pct']}%")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLM Routing Engine — benchmark runner")
    parser.add_argument("--prompts", default="benchmark/prompts.json", type=Path)
    parser.add_argument("--output", default="benchmark/results.json", type=Path)
    args = parser.parse_args()
    main(args.prompts, args.output)
