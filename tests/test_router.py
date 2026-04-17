from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_simple_prompt_routes_to_cheap() -> None:
    response = client.post(
        "/v1/route/infer",
        json={"prompt": "Summarize this short note in one line."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"]["selected_tier"] == "cheap"
    assert body["estimated_cost_usd"] >= 0


def test_complex_prompt_routes_to_premium() -> None:
    prompt = (
        "Analyze the architecture trade-offs between event-driven and request-response systems, "
        "compare their failure handling patterns, and propose a step-by-step migration strategy."
    )
    response = client.post("/v1/route/infer", json={"prompt": prompt})
    assert response.status_code == 200
    body = response.json()
    assert body["route"]["selected_tier"] == "premium"


def test_cheap_fallback_to_premium_on_failure() -> None:
    response = client.post(
        "/v1/route/infer",
        json={"prompt": "Short prompt FORCE_FAIL_CHEAP"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is True
    assert body["route"]["selected_tier"] == "premium"


def test_metrics_summary_shape() -> None:
    response = client.get("/v1/metrics/summary")
    assert response.status_code == 200
    body = response.json()
    assert "total_requests" in body
    assert "by_tier" in body
