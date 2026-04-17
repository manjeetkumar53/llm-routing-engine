from __future__ import annotations

from enum import Enum


class ExperimentMode(str, Enum):
    ROUTER_V1 = "router_v1"       # score-based routing (default)
    ALWAYS_CHEAP = "always_cheap"  # force cheap tier — useful as baseline
    ALWAYS_PREMIUM = "always_premium"  # force premium tier — quality ceiling
