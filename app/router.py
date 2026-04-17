from __future__ import annotations

import time

from app.config import Settings
from app.experiment import ExperimentMode
from app.models import QualityScore, RouteDecision, RouteResponse, UsageData
from app.providers.mock_provider import MockLLMProvider
from app.reliability import CircuitBreaker, CircuitBreakerOpen, retry_with_backoff
from app.services.complexity import score_prompt_complexity
from app.services.costing import estimate_cost_usd
from app.services.evaluation import score_completion
from app.services.telemetry import InMemoryTelemetryStore, TelemetryEvent


class RoutingEngine:
    def __init__(
        self,
        settings: Settings,
        provider: MockLLMProvider,
        telemetry: InMemoryTelemetryStore,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._telemetry = telemetry
        self._breaker = breaker or CircuitBreaker()

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
            completion, in_tokens, out_tokens = retry_with_backoff(
                self._breaker.call,
                self._provider.complete,
                route.selected_tier,
                prompt,
                max_attempts=2,
            )
        except CircuitBreakerOpen:
            # Fail open: use premium if breaker is open on cheap side
            if route.selected_tier == "cheap":
                fallback_used = True
                route = self._select_tier(prompt, ExperimentMode.ALWAYS_PREMIUM)
                route.reason_codes.append("circuit_breaker_open_fallback")
                completion, in_tokens, out_tokens = self._provider.complete("premium", prompt)
            else:
                raise
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

        event = TelemetryEvent(
            selected_tier=route.selected_tier,
            latency_ms=latency_ms,
            estimated_cost_usd=cost,
            experiment_mode=mode.value,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            complexity_score=route.complexity_score,
        )
        self._telemetry.add(event)

        # Derive expected tier from complexity for inline quality scoring
        expected_tier = (
            "premium"
            if route.complexity_score >= self._settings.complexity_threshold
            else "cheap"
        )
        quality_raw = score_completion(
            prompt=prompt,
            completion=completion,
            selected_tier=route.selected_tier,
            expected_tier=expected_tier,
        )

        return RouteResponse(
            request_id=event.request_id,
            route=route,
            completion=completion,
            usage=UsageData(input_tokens=in_tokens, output_tokens=out_tokens),
            latency_ms=latency_ms,
            estimated_cost_usd=cost,
            fallback_used=fallback_used,
            experiment_mode=mode.value,
            quality=QualityScore(**quality_raw),
        )
