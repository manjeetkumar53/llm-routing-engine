from __future__ import annotations

import pytest

from app.reliability import CircuitBreaker, CircuitBreakerOpen, retry_with_backoff


def test_circuit_breaker_starts_closed() -> None:
    cb = CircuitBreaker(failure_threshold=3)
    assert cb.state.value == "closed"


def test_circuit_breaker_opens_after_threshold() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=999)

    def bad_fn():
        raise RuntimeError("fail")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(bad_fn)

    assert cb.state.value == "open"


def test_circuit_breaker_open_raises_breaker_error() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout_s=999)

    def bad_fn():
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        cb.call(bad_fn)

    with pytest.raises(CircuitBreakerOpen):
        cb.call(bad_fn)


def test_circuit_breaker_resets_on_success() -> None:
    cb = CircuitBreaker(failure_threshold=3)

    def good_fn():
        return 42

    cb.call(good_fn)
    assert cb.state.value == "closed"


def test_retry_with_backoff_succeeds_eventually() -> None:
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("not yet")
        return "ok"

    result = retry_with_backoff(flaky, max_attempts=3, base_delay_s=0.0)
    assert result == "ok"
    assert calls["count"] == 3


def test_retry_with_backoff_raises_after_max_attempts() -> None:
    def always_fail():
        raise RuntimeError("always")

    with pytest.raises(RuntimeError, match="always"):
        retry_with_backoff(always_fail, max_attempts=3, base_delay_s=0.0)


def test_circuit_breaker_status_endpoint(client) -> None:
    response = client.get("/v1/circuit-breaker/status")
    assert response.status_code == 200
    assert response.json()["state"] in ("closed", "open", "half_open")
