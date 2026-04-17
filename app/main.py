from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from app.config import load_settings
from app.models import MetricsSummary, RouteRequest, RouteResponse
from app.providers.mock_provider import MockLLMProvider
from app.router import RoutingEngine
from app.services.evaluation import score_completion
from app.services.telemetry import TelemetryStore

app = FastAPI(title="LLM Routing Engine", version="0.2.0")

_settings = load_settings()
_provider = MockLLMProvider()
_db_path = Path(os.getenv("TELEMETRY_DB", "telemetry.db"))
_telemetry = TelemetryStore(db_path=_db_path)
_engine = RoutingEngine(settings=_settings, provider=_provider, telemetry=_telemetry)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/route/infer", response_model=RouteResponse)
def infer(payload: RouteRequest) -> RouteResponse:
    return _engine.infer(payload.prompt, mode=payload.experiment_mode)


@app.get("/v1/metrics/summary", response_model=MetricsSummary)
def metrics_summary() -> MetricsSummary:
    return MetricsSummary(**_telemetry.summary())


@app.get("/v1/eval/events")
def eval_events(limit: int = 100) -> list[dict]:
    """Return raw telemetry events for offline analysis."""
    events = _telemetry.all_events()
    return events[-limit:]
