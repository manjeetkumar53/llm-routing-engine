from __future__ import annotations

from fastapi import FastAPI

from app.config import load_settings
from app.models import MetricsSummary, RouteRequest, RouteResponse
from app.providers.mock_provider import MockLLMProvider
from app.router import RoutingEngine
from app.services.telemetry import InMemoryTelemetryStore

app = FastAPI(title="LLM Routing Engine", version="0.1.0")

_settings = load_settings()
_provider = MockLLMProvider()
_telemetry = InMemoryTelemetryStore()
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
