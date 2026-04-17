# LLM Routing Engine

A production-style starter for cost-aware LLM routing.

## What this does

- Scores prompt complexity.
- Routes requests to `cheap` or `premium` model tier.
- Falls back from cheap to premium on provider failure.
- Tracks latency, tokens, and estimated request cost.
- Exposes summary metrics over HTTP.

## Architecture (v1)

1. API receives prompt.
2. Complexity scorer computes a score in `[0, 1]`.
3. Router selects model tier using threshold policy.
4. Provider executes completion.
5. Telemetry records route, latency, token usage, and cost.

## Local run

```bash
cd /Users/manjeetkumar/Documents/ai-repos/llm-routing-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Example request

```bash
curl -X POST "http://127.0.0.1:8000/v1/route/infer" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Summarize this short email into 3 bullet points."}'
```

## Test

```bash
pytest -q
```

## Next steps

- Replace mock provider with real OpenAI/Claude/Ollama adapters.
- Add experiment mode (`always_premium` vs `router_v1`).
- Store telemetry in PostgreSQL for dashboarding.
