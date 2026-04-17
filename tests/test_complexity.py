from __future__ import annotations

import pytest

from app.services.complexity import score_prompt_complexity


@pytest.mark.parametrize(
    "prompt,expected_tier",
    [
        ("What is Python?", "cheap"),
        ("List the capitals of Europe.", "cheap"),
        ("Summarize this paragraph in one sentence.", "cheap"),
        (
            "Analyze the architecture trade-offs between event-driven and request-response systems, "
            "compare their failure handling patterns, and propose a step-by-step migration strategy.",
            "premium",
        ),
        (
            "Debug this concurrency issue and optimize the locking strategy for high-throughput writes. "
            "Explain why the current design causes deadlocks and propose refactored alternatives.",
            "premium",
        ),
        (
            "Compare the pros and cons of relational vs document databases for a scalable e-commerce platform.",
            "premium",
        ),
    ],
)
def test_score_bounds_and_direction(prompt: str, expected_tier: str) -> None:
    score, reasons = score_prompt_complexity(prompt)
    assert 0.0 <= score <= 1.0, f"score {score} out of bounds"
    assert len(reasons) >= 1
    threshold = 0.50
    inferred_tier = "premium" if score >= threshold else "cheap"
    assert inferred_tier == expected_tier, (
        f"Expected {expected_tier}, got {inferred_tier} (score={score}, reasons={reasons})"
    )


def test_empty_prompt_returns_zero() -> None:
    score, reasons = score_prompt_complexity("  ")
    assert score == 0.0
    assert "empty_prompt" in reasons


def test_simplicity_hints_lower_score() -> None:
    complex_base = (
        "Analyze the trade-offs and compare design strategies for distributed caching architectures."
    )
    simple_variant = "Summarize the following short note."
    score_complex, _ = score_prompt_complexity(complex_base)
    score_simple, _ = score_prompt_complexity(simple_variant)
    assert score_complex > score_simple
