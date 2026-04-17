"""
Circuit breaker + retry-with-backoff for provider calls.

States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (probe)
"""
from __future__ import annotations

import time
from enum import Enum
from threading import Lock
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_s: float = 30.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout_s = recovery_timeout_s
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._state = BreakerState.CLOSED
        self._lock = Lock()

    @property
    def state(self) -> BreakerState:
        return self._state

    def _trip(self) -> None:
        self._state = BreakerState.OPEN
        self._last_failure_time = time.monotonic()

    def _reset(self) -> None:
        self._failure_count = 0
        self._state = BreakerState.CLOSED

    def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            if self._state == BreakerState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self._recovery_timeout_s:
                    self._state = BreakerState.HALF_OPEN
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker OPEN — retry after {self._recovery_timeout_s - elapsed:.1f}s"
                    )

        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            with self._lock:
                self._failure_count += 1
                if self._failure_count >= self._failure_threshold:
                    self._trip()
            raise exc
        else:
            with self._lock:
                self._reset()
            return result


def retry_with_backoff(
    fn: Callable,
    *args: Any,
    max_attempts: int = 3,
    base_delay_s: float = 0.1,
    exceptions: tuple = (RuntimeError,),
    **kwargs: Any,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except exceptions as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                time.sleep(base_delay_s * (2**attempt))
    raise last_exc  # type: ignore[misc]
