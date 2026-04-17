from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TelemetryEvent:
    selected_tier: str
    latency_ms: float
    estimated_cost_usd: float


class InMemoryTelemetryStore:
    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def add(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def summary(self) -> dict:
        total = len(self._events)
        if total == 0:
            return {
                "total_requests": 0,
                "by_tier": {"cheap": 0, "premium": 0},
                "average_latency_ms": 0.0,
                "average_cost_usd": 0.0,
            }

        by_tier = {"cheap": 0, "premium": 0}
        total_latency = 0.0
        total_cost = 0.0
        for event in self._events:
            by_tier[event.selected_tier] = by_tier.get(event.selected_tier, 0) + 1
            total_latency += event.latency_ms
            total_cost += event.estimated_cost_usd

        return {
            "total_requests": total,
            "by_tier": by_tier,
            "average_latency_ms": round(total_latency / total, 2),
            "average_cost_usd": round(total_cost / total, 8),
        }
