# LLM Routing Engine

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.116-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-31%20passing-2ea44f?style=flat-square&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square" />
</p>

Policy-driven LLM routing for teams that want lower cost without blindly downgrading quality. The service scores prompt complexity, chooses a cheap or premium tier, executes with reliability guards, and records telemetry for every request.

It is built around one practical question: should this prompt really hit the expensive model?

---

## What It Does

- Scores each prompt with a weighted complexity heuristic
- Routes to `cheap` or `premium` based on a configurable threshold
- Supports `router_v1`, `always_cheap`, and `always_premium` experiment modes
- Adds retry, circuit breaker, and cheap-to-premium fallback behavior
- Persists telemetry in SQLite with request IDs, cost, latency, tokens, and mode
- Exposes metrics and raw event endpoints for analysis
- Includes a Streamlit dashboard and a benchmark harness
- Can run with the bundled mock provider or real providers: Ollama, OpenAI, Anthropic

---

## Request Flow

```text
prompt
  -> complexity scorer
  -> routing policy
  -> provider call (retry + circuit breaker)
  -> fallback if needed
  -> telemetry + inline quality scoring
  -> response with cost, tier, quality, request_id
```

Core response fields from `POST /v1/route/infer`:

- `route.selected_tier`
- `route.complexity_score`
- `route.reason_codes`
- `estimated_cost_usd`
- `latency_ms`
- `quality.total`
- `request_id`

---

## Benchmark Snapshot

The repository includes a 50-prompt labeled benchmark dataset and a benchmark runner that compares all three routing modes.

Important: the checked-in benchmark numbers are produced with the bundled mock provider and configured token prices. They are useful for validating routing behavior and cost math, not as a claim about real-model quality.

| Policy | Routing Accuracy | Cost / 50 Requests | vs Always Premium |
|---|---:|---:|---:|
| `router_v1` | 80.0% | $0.004313 | -65.6% |
| `always_cheap` | 60.0% | $0.000465 | -96.3% |
| `always_premium` | 40.0% | $0.012525 | baseline |

Takeaway: forcing everything to the cheapest model is not the same as optimizing cost. The point of the router is to reduce spend while preserving acceptable routing quality.

---

## Quick Start

```bash
git clone https://github.com/manjeetkumar53/llm-routing-engine.git
cd llm-routing-engine

python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run with the default mock provider:

```bash
uvicorn app.main:app --reload
```

Open:

- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/v1/route/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain vector databases in simple terms."}'
```

---

## Run With Real LLMs

Provider selection is environment-driven. The app reads `LLM_PROVIDER` at startup and instantiates the correct provider automatically.

Supported values:

- `mock`
- `ollama`
- `openai`
- `anthropic`

### Ollama

Best option for local testing.

```bash
ollama pull llama3.2:1b
ollama pull llama3.1:8b

export LLM_PROVIDER=ollama
uvicorn app.main:app --reload
```

Optional overrides:

```bash
export OLLAMA_CHEAP_MODEL=llama3.2:1b
export OLLAMA_PREMIUM_MODEL=llama3.1:8b
export OLLAMA_BASE_URL=http://localhost:11434/api/chat
```

### OpenAI

Install the SDK first because it is intentionally optional.

```bash
pip install openai
export OPENAI_API_KEY=sk-...
export LLM_PROVIDER=openai
uvicorn app.main:app --reload
```

Default mapping in the provider:

- cheap: `gpt-4o-mini`
- premium: `gpt-4o`

### Anthropic

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export LLM_PROVIDER=anthropic
uvicorn app.main:app --reload
```

Default mapping in the provider:

- cheap: `claude-haiku-4-5`
- premium: `claude-opus-4-5`

### Pricing Configuration

Cost reporting depends on your configured token prices. Update the values to match the models you actually use.

```env
CHEAP_INPUT_PRICE_PER_1M=0.15
CHEAP_OUTPUT_PRICE_PER_1M=0.60
PREMIUM_INPUT_PRICE_PER_1M=5.00
PREMIUM_OUTPUT_PRICE_PER_1M=15.00
```

---

## How To Test It

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

Simple prompt, usually cheap:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/route/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is machine learning?"}'
```

Complex prompt, usually premium:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/route/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Design a scalable event-driven microservice architecture for a fintech platform and compare the trade-offs of CQRS and event sourcing."}'
```

Force experiment modes:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/route/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain Kubernetes autoscaling.","experiment_mode":"always_cheap"}'

curl -s -X POST http://127.0.0.1:8000/v1/route/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain Kubernetes autoscaling.","experiment_mode":"always_premium"}'
```

Inspect metrics and telemetry:

```bash
curl -s http://127.0.0.1:8000/v1/metrics/summary
curl -s "http://127.0.0.1:8000/v1/eval/events?limit=20"
curl -s http://127.0.0.1:8000/v1/circuit-breaker/status
```

Run the automated tests:

```bash
pytest -q
```

Run the benchmark harness:

```bash
python -m benchmark.run
```

Open the dashboard:

```bash
streamlit run dashboard/app.py
```

---

## API Surface

| Endpoint | Purpose |
|---|---|
| `POST /v1/route/infer` | Route a prompt and return completion, cost, quality, and routing details |
| `GET /health` | Basic service liveness |
| `GET /v1/metrics/summary` | Aggregate metrics by tier and experiment mode |
| `GET /v1/eval/events` | Raw telemetry events for offline analysis |
| `GET /v1/circuit-breaker/status` | Current breaker state |
| `GET /docs` | Swagger / OpenAPI UI |

Example request:

```json
{
  "prompt": "Analyze the trade-offs between CQRS and event sourcing for a banking system.",
  "experiment_mode": "router_v1"
}
```

Example response shape:

```json
{
  "request_id": "3f8a2c14-91e7-4b2d-bc43-7a1d9e204f88",
  "route": {
    "selected_tier": "premium",
    "complexity_score": 0.725,
    "reason_codes": ["complexity_hints_present", "threshold=0.5"]
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

---

## Configuration

The app reads configuration from environment variables.

```env
LLM_PROVIDER=mock

# Optional API keys
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# Optional Ollama overrides
# OLLAMA_BASE_URL=http://localhost:11434/api/chat
# OLLAMA_CHEAP_MODEL=llama3.2:1b
# OLLAMA_PREMIUM_MODEL=llama3.1:8b

ROUTER_COMPLEXITY_THRESHOLD=0.50

CHEAP_INPUT_PRICE_PER_1M=0.15
CHEAP_OUTPUT_PRICE_PER_1M=0.60
PREMIUM_INPUT_PRICE_PER_1M=5.00
PREMIUM_OUTPUT_PRICE_PER_1M=15.00

TELEMETRY_DB=telemetry.db
```

---

## Design Notes

**Why a rule-based scorer?**

The scorer is transparent, cheap to run, and easy to tune. Every routing decision returns `reason_codes`, which makes behavior inspectable during development and evaluation.

**Why an inline quality proxy instead of LLM-as-judge?**

The built-in quality score is designed for request-time feedback without adding another expensive model call. It is intentionally lightweight and should be treated as a proxy signal, not a final judgment layer.

**Why SQLite?**

For a small service or prototype, SQLite removes operational overhead while still preserving useful request history and aggregate metrics.

**Where does reliability live?**

Retry, circuit breaker, and fallback behavior live in the routing engine layer so decisions can account for the selected tier and the current experiment mode.

---

## Project Structure

```text
app/
  config.py
  experiment.py
  main.py
  middleware.py
  models.py
  reliability.py
  router.py
  providers/
    anthropic_provider.py
    mock_provider.py
    ollama_provider.py
    openai_provider.py
  services/
    complexity.py
    costing.py
    evaluation.py
    telemetry.py

benchmark/
  prompts.json
  results.json
  run.py

dashboard/
  app.py

tests/
  conftest.py
  test_complexity.py
  test_evaluation.py
  test_reliability.py
  test_router.py
```

---

## License

MIT

