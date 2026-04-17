from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceConfig:
    input_price_per_1m: float
    output_price_per_1m: float


@dataclass(frozen=True)
class Settings:
    complexity_threshold: float
    prices: dict[str, PriceConfig]


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def load_settings() -> Settings:
    return Settings(
        complexity_threshold=_read_float("ROUTER_COMPLEXITY_THRESHOLD", 0.50),
        prices={
            "cheap": PriceConfig(
                input_price_per_1m=_read_float("CHEAP_INPUT_PRICE_PER_1M", 0.15),
                output_price_per_1m=_read_float("CHEAP_OUTPUT_PRICE_PER_1M", 0.60),
            ),
            "premium": PriceConfig(
                input_price_per_1m=_read_float("PREMIUM_INPUT_PRICE_PER_1M", 5.00),
                output_price_per_1m=_read_float("PREMIUM_OUTPUT_PRICE_PER_1M", 15.00),
            ),
        },
    )
