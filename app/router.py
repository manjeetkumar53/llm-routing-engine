from __future__ import annotations

import time

from app.config import Settings
from app.experiment import ExperimentMode
from app.models import RouteDecision, RouteResponse, UsageData
from app.providers.mock_provider import MockLLMProvider
from app.services.complexity import score_prompt_complexity
from app.services.costing import estimate_cost_usd
from app.services.telemetry import InMemoryTelemetryStore, TelemetryEvent


class RoutingEngine:
    def __init__(
        self,
        settings: Settings,
        provider: MockLLMProvider,
        telemetry: InMemoryTelemetryStore,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._telemetry = telemetry

    def _select_tier(
        self,
        prompt: str,
        mode: ExperimentMode,
    ) -> RouteDecision:
        score, reason_codes = score_prompt_complexity(prompt)

        if mode == ExperimentMode.ALWAYS_PREMIUM:
            selected_tier = "premium"
            reason_codes = ["experiment_always_premium"]
        elif mode == ExperimentMode.ALWAYS_CHEAP:
            selected_tier = "cheap"
            reason_codes = ["experiment_always_cheap"]
        else:
            selected_tier = "premium" if score >= self._settings.complexity_threshold else "cheap"
            reason_codes.append(f"threshold={self._settings.complexity_threshold}")

        return RouteDecision(
            selected_tier=selected_tier,
            reason_codes=reason_codes,
            complexity_score=round(score, 4),
        )

    def infer(
        self,
        prompt: str,
        mode: ExperimentMode = ExperimentMode.ROUTER_V1,
    ) -> RouteResponse:
        route = self._select_tier(prompt, mode)
        fallback_used = False
        start = time.perf_counter()

        try:
            completion, in_tokens, out_tokens = self._provider.complete(route.selected_tier, prompt)
        except RuntimeError:
            if route.selected_tier != "cheap":
                raise
            fallback_used = True
            route.selected_tier = "premium"
            route.reason_codes.append("cheap_failed_fallback_to_premium")
            completion, in_tokens, out_tokens = self._provider.complete("premium", prompt)

        latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
        price = self._settings.prices[route.selected_tier]
        cost = estimate_cost_usd(in_tokens, out_tokens, price)

        self._telemetry.add(
            TelemetryEvent(
                selected_tier=route.selected_tier,
                latency_ms=latency_ms,
                estimated_cost_usd=cost,
                experiment_mode=mode.value,
            )
        )

        return RouteResponse(
            route=route,
            completion=completion,
            usage=UsageData(input_tokens=in_tokens, output_tokens=out_tokens),
            latency_ms=latency_ms,
            estimated_cost_usd=cost,
            fallback_used=fallback_used,
            experiment_mode=mode.value,
        )
