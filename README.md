# LLM Routing Engine

> **Policy-driven LLM routing that reduces inference cost by ~65% while maintaining quality and reliability.**

A production-grade service that classifies prompt complexity, routes requests to the cheapest viable model tier, tracks cost/latency/quality per request, and exposes a live analytics dashboard — all with circuit-breaker protection and structured observability.

---

## Why this exists

Most teams send every prompt to the most expensive model. This is wasteful: simple questions ("What is Python?") don't need GPT-4 level reasoning. Complex analytical prompts do.

This engine automatically routes to the right tier, measures the outcome, and lets you A/B test routing policies — so you can make cost/quality trade-offs with data, not guesses.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     FastAPI Service                        │
│                                                            │
│  POST /v1/route/infer                                      │
│       │                                                    │
│       ▼                                                    │
│  ┌─────────────────┐     ┌──────────────────────────────┐ │
│  │ Complexity Scorer│────▶│    Routing Policy Engine     │ │
│  │                  │     │  router_v1 | always_cheap    │ │
│  │ • Keyword weights│     │  | always_premium            │ │
│  │ • Length signal  │     └──────────────┬───────────────┘ │
│  │ • Sentence count │                    │                 │
│  └─────────────────┘          ┌──────────▼────────┐       │
│                                │  Circuit Breaker  │       │
│                                │  + Retry Backoff  │       │
│                                └──────────┬────────┘       │
│                          ┌────────────────▼──────────────┐ │
│                          │       Model Provider           │ │
│                          │  cheap tier  │  premium tier  │ │
│                          └──────┬───────┴───────┬────────┘ │
│                                 │               │          │
│  ┌──────────────────────────────▼───────────────▼────────┐ │
│  │              Telemetry + Evaluation                    │ │
│  │  • SQLite persistence  • Quality scoring               │ │
│  │  • Cost estimation     • Request ID tracing            │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘

GET /v1/metrics/summary   → aggregated stats by tier + experiment mode
GET /v1/eval/events       → raw telemetry events
GET /v1/circuit-breaker/status → breaker state
streamlit run dashboard/app.py → live analytics dashboard
python -m benchmark.run        → cost/quality benchmark report
```

---

## Measured results (50-prompt benchmark)

| Mode | Routing Accuracy | Total Cost | vs Premium |
|---|---|---|---|
| `router_v1` | **80%** | $0.004313 | **−65.6% cost** |
| `always_cheap` | 60% | $0.000465 | −96.3% cost |
| `always_premium` | 40% | $0.012525 | baseline |

> Router saves 65.6% cost vs always-premium while maintaining 80% routing accuracy.  
> always_cheap scores lower accuracy because it under-provisions complex prompts.

---

## Features

| Layer | What's built |
|---|---|
| **Routing** | Weighted complexity scorer (16 signals) with A/B experiment modes |
| **Fallback** | Cheap → Premium automatic fallback on provider failure |
| **Reliability** | Circuit breaker (CLOSED/OPEN/HALF\_OPEN) + retry with exponential backoff |
| **Cost tracking** | Per-request token cost at configurable per-model pricing |
| **Quality scoring** | Keyword recall + length ratio + tier alignment proxy score |
| **Telemetry** | SQLite-persisted events with request ID, timestamps, all metrics |
| **Dashboard** | Streamlit: 6 charts — tier split, cost trend, latency histogram, mode comparison, benchmark comparison |
| **Observability** | Structured JSON logs, X-Request-ID header propagation |
| **API docs** | Auto-generated Swagger at `/docs` |

---

## Local setup

```bash
git clone https://github.com/manjeetkumar53/llm-routing-engine.git
cd llm-routing-engine

python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start API
uvicorn app.main:app --reload
# → http://127.0.0.1:8000/docs
```

---

## Usage examples

### Route a prompt (default: router_v1)
```bash
curl -X POST http://127.0.0.1:8000/v1/route/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is a circuit breaker pattern?"}'
```

### Force premium tier (A/B baseline)
```bash
curl -X POST http://127.0.0.1:8000/v1/route/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize this note.", "experiment_mode": "always_premium"}'
```

### View live metrics
```bash
curl http://127.0.0.1:8000/v1/metrics/summary
```

### Run benchmark (generates benchmark/results.json)
```bash
python -m benchmark.run
```

### Open dashboard
```bash
streamlit run dashboard/app.py
```

---

## Experiment modes

| Mode | Behaviour | Use for |
|---|---|---|
| `router_v1` | Score-based routing (default) | Production |
| `always_cheap` | Force cheap model | Cost floor baseline |
| `always_premium` | Force premium model | Quality ceiling baseline |

---

## API response shape

```json
{
  "request_id": "uuid-here",
  "route": {
    "selected_tier": "cheap",
    "complexity_score": 0.1234,
    "reason_codes": ["short_prompt", "threshold=0.5"]
  },
  "completion": "...",
  "usage": {"input_tokens": 12, "output_tokens": 18},
  "latency_ms": 1.23,
  "estimated_cost_usd": 0.0000043,
  "fallback_used": false,
  "experiment_mode": "router_v1",
  "quality": {
    "keyword_recall": 0.75,
    "length_ratio": 0.9,
    "tier_alignment": 1.0,
    "total": 0.855,
    "acceptable": true
  }
}
```

---

## Configuration (.env)

```env
ROUTER_COMPLEXITY_THRESHOLD=0.50        # Score >= this → premium
CHEAP_INPUT_PRICE_PER_1M=0.15          # USD per 1M input tokens
CHEAP_OUTPUT_PRICE_PER_1M=0.60
PREMIUM_INPUT_PRICE_PER_1M=5.00
PREMIUM_OUTPUT_PRICE_PER_1M=15.00
TELEMETRY_DB=telemetry.db              # SQLite path
```

---

## Trade-offs and design decisions

**Why SQLite instead of PostgreSQL?**  
For v1, SQLite removes operational overhead and is sufficient for 10K events/day. Migrating to Postgres is a drop-in change to the connection string — the schema and queries are standard SQL.

**Why a proxy quality scorer instead of LLM-judge?**  
LLM-as-judge adds latency and cost to every request. The proxy (keyword recall + length + tier alignment) is sufficient for regression testing and catches obvious degradation. A real LLM judge can be added as a post-hoc batch eval step.

**Why circuit breaker at the engine level, not the provider level?**  
The engine owns fallback logic (cheap → premium). Having the breaker here means fallback decisions are made with full context — including whether we're already in a fallback path.

**Why rule-based routing instead of ML classifier?**  
Rule-based is explainable, zero-latency, and debuggable. The scoring system is parameterized so weights can be tuned with data. An ML classifier would be the next upgrade once you have 10K+ labeled routing decisions.

---

## What I would build next

- [ ] Real provider adapters: OpenAI, Anthropic, Ollama
- [ ] ML complexity classifier trained on routing decision data
- [ ] PostgreSQL backend for production scale
- [ ] LLM-judge quality eval as async batch job
- [ ] Prometheus metrics endpoint + Grafana integration
- [ ] Rate limiter per API key
- [ ] Streaming response support

---

## Tests

```bash
pytest -v         # 31 tests: routing, complexity, reliability, evaluation, API
```

---

## Project structure

```
app/
  config.py           # Settings from env
  experiment.py       # ExperimentMode enum
  main.py             # FastAPI app + endpoints
  middleware.py       # Structured JSON logging + request ID
  models.py           # Pydantic models
  reliability.py      # Circuit breaker + retry-with-backoff
  router.py           # RoutingEngine
  providers/
    mock_provider.py  # Swappable provider interface
  services/
    complexity.py     # Weighted prompt complexity scorer
    costing.py        # Per-request cost estimation
    evaluation.py     # Quality proxy scoring
    telemetry.py      # SQLite-backed event store
benchmark/
  prompts.json        # 50-prompt labeled dataset
  run.py              # Benchmark runner with report
  results.json        # Latest benchmark output
dashboard/
  app.py              # Streamlit analytics dashboard
tests/                # 31 tests across all modules
```

