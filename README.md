# LLM Routing Engine

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.116-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-31%20passing-2ea44f?style=flat-square&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/Cost%20Reduction-65.6%25-FF6B35?style=flat-square" />
  <img src="https://img.shields.io/badge/Routing%20Accuracy-80%25-6554C0?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square" />
</p>

<br/>

**A production-grade, policy-driven LLM routing service.** Classifies prompt complexity at request time, routes to the cheapest viable model tier, measures cost and output quality per request, and supports A/B experimentation across routing policies — with circuit-breaker reliability and structured observability throughout.

Built to answer one question most teams avoid: *are we using the right model for each request, or just the most expensive one?*

---

## How It Works

Every request passes through four stages:

```
Prompt
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Complexity Scoring                                          │
│     16 weighted signals: keyword intent, length, sentence       │
│     density, question count → score in [0.0, 1.0]              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Routing Policy                                              │
│     score ≥ threshold  →  premium tier                         │
│     score  < threshold  →  cheap tier                           │
│     experiment_mode override: always_cheap | always_premium     │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Reliable Provider Call                                      │
│     Circuit breaker (CLOSED → OPEN → HALF_OPEN)                │
│     Retry with exponential backoff                              │
│     Auto-fallback: cheap failure → premium                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Telemetry + Evaluation                                      │
│     SQLite persistence · per-request cost · quality proxy       │
│     request_id tracing · structured JSON logs                   │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
Response: completion + route decision + cost + quality score + request_id
```

---

## Benchmark Results

Evaluated on a labeled dataset of 50 prompts spanning simple factual queries through complex multi-step architectural analysis.

| Policy | Routing Accuracy | Cost / 50 Requests | vs Always-Premium |
|---|---|---|---|
| **`router_v1`** | **80%** | **$0.004313** | **−65.6%** |
| `always_cheap` | 60% | $0.000465 | −96.3% |
| `always_premium` | 40% | $0.012525 | baseline |

**Key finding:** `always_cheap` is not the answer — it under-provisions complex prompts and degrades output quality. `router_v1` finds the optimal operating point: the cheapest routing that keeps quality acceptable.

---

## System Design

```
┌────────────────────────────────────────────────────────────────────┐
│                          FastAPI Service                           │
│                                                                    │
│   POST /v1/route/infer          GET /v1/metrics/summary            │
│   GET  /v1/eval/events          GET /v1/circuit-breaker/status     │
│                                 GET /health                        │
│                                                                    │
│  RequestLoggingMiddleware                                          │
│  → X-Request-ID propagation · X-Latency-MS · structured JSON logs │
│                                                                    │
│  ┌──────────────────┐    ┌──────────────────────────────────────┐  │
│  │ ComplexityScorer │───▶│         RoutingEngine                │  │
│  │                  │    │                                      │  │
│  │ Keyword weights  │    │  ExperimentMode:                     │  │
│  │ Length signal    │    │    router_v1 (default)               │  │
│  │ Sentence count   │    │    always_cheap                      │  │
│  │ Question density │    │    always_premium                    │  │
│  │ Simplicity hints │    └────────────────┬─────────────────────┘  │
│  └──────────────────┘                     │                        │
│                                           ▼                        │
│                              ┌────────────────────────┐            │
│                              │    CircuitBreaker      │            │
│                              │  CLOSED→OPEN→HALF_OPEN │            │
│                              │  + retry backoff       │            │
│                              └──────────┬─────────────┘            │
│                                         │                          │
│                              ┌──────────▼─────────────┐            │
│                              │    Model Provider       │            │
│                              │  cheap  │  premium      │            │
│                              └──────────┬──────────────┘            │
│                                         │                          │
│  ┌──────────────────────────────────────▼───────────────────────┐  │
│  │                  Telemetry Store (SQLite)                    │  │
│  │  request_id · created_at · tier · cost · latency · tokens   │  │
│  │  complexity_score · experiment_mode · quality_score          │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────▼──────────────┐
                    │   Streamlit Dashboard         │
                    │  Tier split · Cost trend      │
                    │  Latency dist · Mode compare  │
                    │  Benchmark: cost vs accuracy  │
                    └───────────────────────────────┘
```

---

## API

### `POST /v1/route/infer`

Routes a prompt and returns routing decision, completion, cost, quality, and tracing metadata.

**Request**
```json
{
  "prompt": "Analyze the trade-offs between CQRS and event sourcing for a banking system.",
  "experiment_mode": "router_v1"
}
```

**Response**
```json
{
  "request_id": "3f8a2c14-91e7-4b2d-bc43-7a1d9e204f88",
  "route": {
    "selected_tier": "premium",
    "complexity_score": 0.7250,
    "reason_codes": ["complexity_hints_present", "multi_sentence", "threshold=0.5"]
  },
  "completion": "...",
  "usage": {
    "input_tokens": 24,
    "output_tokens": 187
  },
  "latency_ms": 312.5,
  "estimated_cost_usd": 0.00003125,
  "fallback_used": false,
  "experiment_mode": "router_v1",
  "quality": {
    "keyword_recall": 0.82,
    "length_ratio": 1.0,
    "tier_alignment": 1.0,
    "total": 0.927,
    "acceptable": true
  }
}
```

### Other endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Service health check |
| `GET /v1/metrics/summary` | Aggregated stats by tier and experiment mode |
| `GET /v1/eval/events?limit=100` | Paginated raw telemetry events |
| `GET /v1/circuit-breaker/status` | Current breaker state |
| `GET /docs` | Auto-generated OpenAPI / Swagger UI |

---

## Experiment Modes

Each request can declare an `experiment_mode` to override the routing policy. This enables controlled A/B testing between policies without changing service configuration.

| Mode | Behaviour |
|---|---|
| `router_v1` | Complexity-scored routing (production default) |
| `always_cheap` | Force cheap tier — cost floor baseline |
| `always_premium` | Force premium tier — quality ceiling baseline |

Telemetry records the mode on every event. The metrics summary breaks down cost and request counts by mode, so you can compare policies with real traffic.

---

## Quality Scoring

Every response includes a quality proxy score computed at inference time — no external LLM judge required.

| Signal | Weight | Description |
|---|---|---|
| `keyword_recall` | 40% | Key terms from the prompt present in the completion |
| `length_ratio` | 30% | Completion length relative to tier-appropriate floor |
| `tier_alignment` | 30% | Penalty when a complex prompt is routed to cheap tier |

A score ≥ 0.70 is considered acceptable. Scores below threshold flag potential routing mistakes for review.

---

## Reliability

The provider call path is hardened at three levels:

1. **Retry with exponential backoff** — transient failures are retried up to N times before escalating
2. **Circuit breaker** — trips after N consecutive failures; enters HALF_OPEN after a recovery timeout to probe health before resuming traffic
3. **Automatic tier fallback** — cheap tier failure triggers an immediate retry on premium; circuit breaker open on cheap routes all traffic to premium until recovery

These operate at the routing engine level, not the provider level, so fallback decisions have full context — including whether the request is already on a fallback path.

---

## Running Locally

**Prerequisites:** Python 3.13, git

```bash
git clone https://github.com/manjeetkumar53/llm-routing-engine.git
cd llm-routing-engine

python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Start the API**
```bash
uvicorn app.main:app --reload
# Swagger UI → http://127.0.0.1:8000/docs
```

**Run the benchmark**
```bash
python -m benchmark.run
# Outputs cost savings %, routing accuracy, p95 latency per mode
```

**Open the analytics dashboard**
```bash
streamlit run dashboard/app.py
```

**Run tests**
```bash
pytest -v
# 31 tests: routing decisions, complexity scoring, reliability, quality eval, API contracts
```

---

## Configuration

All settings are read from environment variables. Copy `.env.example` and adjust.

```env
ROUTER_COMPLEXITY_THRESHOLD=0.50       # Prompts scoring >= this route to premium
CHEAP_INPUT_PRICE_PER_1M=0.15         # USD per 1M input tokens (cheap tier)
CHEAP_OUTPUT_PRICE_PER_1M=0.60
PREMIUM_INPUT_PRICE_PER_1M=5.00       # USD per 1M input tokens (premium tier)
PREMIUM_OUTPUT_PRICE_PER_1M=15.00
TELEMETRY_DB=telemetry.db             # SQLite file path
```

---

## Design Decisions

**Rule-based scorer over ML classifier**
A weighted rule system is explainable, zero-latency, and immediately debuggable. Each routing decision includes `reason_codes` so you can trace exactly why a prompt was sent to a given tier. The scoring weights are parameterized; a learned classifier is the natural next step once enough labeled routing decisions accumulate.

**Proxy quality scorer over LLM-as-judge**
Running a judge model on every inference request doubles cost and adds latency on the critical path. The proxy (keyword recall + length + tier alignment) catches the most important class of failure — sending a complex prompt to the cheap model — and operates in microseconds. Post-hoc batch evaluation with an LLM judge remains an option for periodic quality audits.

**Circuit breaker at the engine level, not provider level**
The routing engine owns fallback logic. Placing the breaker here means fallback decisions have full context: which tier was originally selected, whether we're already in a fallback path, and what the current experiment mode is.

**SQLite for telemetry persistence**
Removes all operational overhead for the initial deployment. The schema is standard SQL; moving to PostgreSQL is a connection string change. At 10K requests/day, SQLite is not the bottleneck.

---

## Project Structure

```
app/
├── config.py              Environment-based settings
├── experiment.py          ExperimentMode enum
├── main.py                FastAPI application and endpoint definitions
├── middleware.py          Structured JSON logging, X-Request-ID propagation
├── models.py              Pydantic request/response models
├── reliability.py         CircuitBreaker + retry_with_backoff
├── router.py              RoutingEngine — orchestrates all layers
└── providers/
│   └── mock_provider.py   Provider interface (swap in real adapters here)
└── services/
    ├── complexity.py       Weighted prompt complexity scorer (16 signals)
    ├── costing.py          Per-request token cost estimation
    ├── evaluation.py       Quality proxy scoring
    └── telemetry.py        SQLite-backed event store

benchmark/
├── prompts.json           50-prompt labeled evaluation dataset
├── run.py                 Benchmark runner: cost, accuracy, latency by mode
└── results.json           Most recent benchmark output

dashboard/
└── app.py                 Streamlit analytics dashboard (6 charts + KPIs)

tests/                     31 tests across all modules
```

---

## License

MIT


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

