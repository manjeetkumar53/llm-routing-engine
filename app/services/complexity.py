from __future__ import annotations

import re


# High-complexity intent keywords — each hit adds weight
_COMPLEXITY_HINTS: list[tuple[str, float]] = [
    (r"\bcompare\b", 0.18),
    (r"\bcontrast\b", 0.12),
    (r"\banalyze\b", 0.14),
    (r"\btrade[- ]?off(s)?\b", 0.15),
    (r"\bdesign\b", 0.10),
    (r"\barchitecture\b", 0.15),
    (r"\bdebug\b", 0.10),
    (r"\boptimi[sz]e\b", 0.12),
    (r"\bstep[- ]?by[- ]?step\b", 0.12),
    (r"\bexplain why\b", 0.12),
    (r"\bpros\b.*\bcons\b", 0.20),
    (r"\bpropose\b", 0.10),
    (r"\bmigrat(e|ion)\b", 0.10),
    (r"\brefactor\b", 0.10),
    (r"\bsecurity\b", 0.08),
    (r"\bscalabl(e|ility)\b", 0.15),
]

# Simple / cheap intent keywords — each hit subtracts weight
_SIMPLICITY_HINTS: list[tuple[str, float]] = [
    (r"\bsummariz(e|ation)\b", 0.10),
    (r"\btranslat(e|ion)\b", 0.08),
    (r"\blist\b", 0.06),
    (r"\bdefine\b", 0.08),
    (r"\bwhat is\b", 0.06),
]


def score_prompt_complexity(prompt: str) -> tuple[float, list[str]]:
    """Return (score_in_0_1, reason_codes) for the given prompt."""
    reasons: list[str] = []
    normalized = prompt.strip()
    if not normalized:
        return 0.0, ["empty_prompt"]

    words = normalized.split()
    word_count = len(words)

    # --- Length signal (up to 0.25 contribution) ---
    length_score = min(len(normalized) / 1500.0, 1.0)
    score = 0.25 * length_score

    # --- Sentence count signal ---
    sentence_count = max(1, len(re.findall(r"[.!?]+", normalized)))
    if sentence_count >= 4:
        score += 0.08
        reasons.append("multi_sentence")

    # --- Complexity keyword hits ---
    complexity_boost = 0.0
    for pattern, weight in _COMPLEXITY_HINTS:
        if re.search(pattern, normalized, re.IGNORECASE):
            complexity_boost += weight
    if complexity_boost > 0:
        reasons.append("complexity_hints_present")
    score += min(complexity_boost, 0.50)

    # --- Simplicity keyword deductions ---
    simplicity_cut = 0.0
    for pattern, weight in _SIMPLICITY_HINTS:
        if re.search(pattern, normalized, re.IGNORECASE):
            simplicity_cut += weight
    if simplicity_cut > 0:
        reasons.append("simplicity_hints_present")
    score -= simplicity_cut

    # --- Short prompt penalty ---
    if word_count < 10:
        reasons.append("short_prompt")
        score -= 0.20

    # --- Question density bonus (many questions = multi-part query) ---
    question_count = normalized.count("?")
    if question_count >= 2:
        reasons.append("multi_question")
        score += 0.08

    bounded = round(max(0.0, min(score, 1.0)), 4)
    if not reasons:
        reasons.append("default_rule")
    return bounded, reasons
