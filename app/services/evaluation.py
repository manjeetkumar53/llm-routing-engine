"""
Evaluation harness: quality proxy scoring for LLM routing decisions.

Scoring uses three signals (no real LLM judge needed for v1):
  1. Keyword recall  — expected keywords present in completion
  2. Length ratio    — completion length relative to a reference floor
  3. Tier alignment  — premium tier gets a bonus for complex prompts

Final score is in [0, 1]. A score >= 0.7 is considered "acceptable".
"""
from __future__ import annotations

import re


ACCEPTABLE_THRESHOLD = 0.70


def score_completion(
    prompt: str,
    completion: str,
    selected_tier: str,
    expected_tier: str,
    reference_keywords: list[str] | None = None,
) -> dict:
    """
    Return a quality score dict with component breakdown.

    Args:
        prompt:             Original prompt text.
        completion:         Model completion text.
        selected_tier:      Tier that was actually used ('cheap' | 'premium').
        expected_tier:      Expected tier based on prompt label.
        reference_keywords: Optional list of words that should appear in completion.

    Returns:
        dict with keys: keyword_recall, length_ratio, tier_alignment, total, acceptable
    """
    completion_lower = completion.lower()

    # --- Keyword recall ---
    if reference_keywords:
        hits = sum(
            1
            for kw in reference_keywords
            if re.search(re.escape(kw.lower()), completion_lower)
        )
        keyword_recall = hits / len(reference_keywords)
    else:
        # Fallback: check if prompt words (>4 chars) appear in completion
        prompt_words = [w for w in re.findall(r"\b\w{5,}\b", prompt.lower())]
        if prompt_words:
            hits = sum(1 for w in prompt_words if w in completion_lower)
            keyword_recall = min(hits / len(prompt_words), 1.0)
        else:
            keyword_recall = 0.5  # neutral

    # --- Length ratio (floor = 20 chars for cheap, 40 for premium) ---
    floor = 40 if expected_tier == "premium" else 20
    length_ratio = min(len(completion) / max(floor, 1), 1.0)

    # --- Tier alignment ---
    # Penalise using cheap tier for a prompt that expects premium
    if expected_tier == "premium" and selected_tier == "cheap":
        tier_alignment = 0.4
    elif expected_tier == "cheap" and selected_tier == "premium":
        tier_alignment = 0.9  # over-provisioning is acceptable, not ideal
    else:
        tier_alignment = 1.0

    total = round(
        0.40 * keyword_recall + 0.30 * length_ratio + 0.30 * tier_alignment,
        4,
    )

    return {
        "keyword_recall": round(keyword_recall, 4),
        "length_ratio": round(length_ratio, 4),
        "tier_alignment": round(tier_alignment, 4),
        "total": total,
        "acceptable": total >= ACCEPTABLE_THRESHOLD,
    }
