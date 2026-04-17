from __future__ import annotations

import re


COMPLEXITY_HINTS = [
    r"\bcompare\b",
    r"\banalyze\b",
    r"\btrade[- ]?off(s)?\b",
    r"\bdesign\b",
    r"\barchitecture\b",
    r"\bdebug\b",
    r"\boptimi[sz]e\b",
    r"\bstep[- ]?by[- ]?step\b",
]


def score_prompt_complexity(prompt: str) -> tuple[float, list[str]]:
    reasons: list[str] = []
    normalized = prompt.strip()
    if not normalized:
        return 0.0, ["empty_prompt"]

    length_score = min(len(normalized) / 1200.0, 1.0)
    score = 0.35 * length_score

    hit_count = sum(1 for pattern in COMPLEXITY_HINTS if re.search(pattern, normalized, re.IGNORECASE))
    if hit_count > 0:
        reasons.append("complexity_hints_present")
    score += min(hit_count * 0.15, 0.45)

    if "?" in normalized and len(normalized) > 300:
        reasons.append("long_question_prompt")
        score += 0.10

    if len(normalized.split()) < 12:
        reasons.append("short_prompt")
        score -= 0.15

    bounded = max(0.0, min(score, 1.0))
    if not reasons:
        reasons.append("default_rule")
    return bounded, reasons
