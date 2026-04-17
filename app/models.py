from __future__ import annotations

from pydantic import BaseModel, Field

from app.experiment import ExperimentMode


class RouteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    experiment_mode: ExperimentMode = ExperimentMode.ROUTER_V1


class RouteDecision(BaseModel):
    selected_tier: str
    reason_codes: list[str]
    complexity_score: float


class UsageData(BaseModel):
    input_tokens: int
    output_tokens: int


class QualityScore(BaseModel):
    keyword_recall: float
    length_ratio: float
    tier_alignment: float
    total: float
    acceptable: bool


class RouteResponse(BaseModel):
    request_id: str
    route: RouteDecision
    completion: str
    usage: UsageData
    latency_ms: float
    estimated_cost_usd: float
    fallback_used: bool
    experiment_mode: str
    quality: QualityScore


class MetricsSummary(BaseModel):
    total_requests: int
    by_tier: dict[str, int]
    average_latency_ms: float
    average_cost_usd: float
    by_experiment_mode: dict[str, int]
