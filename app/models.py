from __future__ import annotations

from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)


class RouteDecision(BaseModel):
    selected_tier: str
    reason_codes: list[str]
    complexity_score: float


class UsageData(BaseModel):
    input_tokens: int
    output_tokens: int


class RouteResponse(BaseModel):
    route: RouteDecision
    completion: str
    usage: UsageData
    latency_ms: float
    estimated_cost_usd: float
    fallback_used: bool


class MetricsSummary(BaseModel):
    total_requests: int
    by_tier: dict[str, int]
    average_latency_ms: float
    average_cost_usd: float
