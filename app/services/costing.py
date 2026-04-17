from __future__ import annotations

from app.config import PriceConfig


def estimate_cost_usd(input_tokens: int, output_tokens: int, price: PriceConfig) -> float:
    input_cost = (input_tokens / 1_000_000.0) * price.input_price_per_1m
    output_cost = (output_tokens / 1_000_000.0) * price.output_price_per_1m
    return round(input_cost + output_cost, 8)
