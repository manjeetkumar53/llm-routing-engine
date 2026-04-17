from __future__ import annotations

import pytest

from app.services.evaluation import score_completion, ACCEPTABLE_THRESHOLD


def test_perfect_alignment_scores_high() -> None:
    result = score_completion(
        prompt="Analyze and compare the pros and cons of microservices architecture.",
        completion=(
            "[premium] Detailed response with stronger reasoning depth and tighter structure. "
            "microservices architecture analysis: pros include scalability, cons include complexity."
        ),
        selected_tier="premium",
        expected_tier="premium",
    )
    assert result["total"] >= ACCEPTABLE_THRESHOLD
    assert result["acceptable"] is True
    assert result["tier_alignment"] == 1.0


def test_wrong_tier_penalises_score() -> None:
    result = score_completion(
        prompt="Design a scalable event-driven fraud detection architecture.",
        completion="[cheap] short response.",
        selected_tier="cheap",
        expected_tier="premium",
    )
    assert result["tier_alignment"] == 0.4
    assert result["total"] < result["tier_alignment"] + 0.5  # penalised


def test_over_provisioning_acceptable() -> None:
    result = score_completion(
        prompt="What is Python?",
        completion="[premium] Detailed response with stronger reasoning depth.",
        selected_tier="premium",
        expected_tier="cheap",
    )
    assert result["tier_alignment"] == 0.9


def test_reference_keywords_scoring() -> None:
    result = score_completion(
        prompt="Compare SQL and NoSQL.",
        completion="SQL is relational. NoSQL is document-based. Both have trade-offs.",
        selected_tier="cheap",
        expected_tier="cheap",
        reference_keywords=["SQL", "NoSQL", "relational"],
    )
    assert result["keyword_recall"] == 1.0


def test_missing_keywords_lower_score() -> None:
    result = score_completion(
        prompt="Compare SQL and NoSQL.",
        completion="Databases are used for data storage.",
        selected_tier="cheap",
        expected_tier="cheap",
        reference_keywords=["SQL", "NoSQL", "relational", "document"],
    )
    assert result["keyword_recall"] < 0.5


def test_score_fields_present() -> None:
    result = score_completion(
        prompt="Hello.",
        completion="Hi there.",
        selected_tier="cheap",
        expected_tier="cheap",
    )
    for key in ("keyword_recall", "length_ratio", "tier_alignment", "total", "acceptable"):
        assert key in result


def test_quality_field_in_api_response(client) -> None:
    response = client.post(
        "/v1/route/infer",
        json={"prompt": "What is a microservice?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "quality" in body
    q = body["quality"]
    assert 0.0 <= q["total"] <= 1.0
    assert isinstance(q["acceptable"], bool)
