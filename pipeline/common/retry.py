"""Retries with exponential backoff, aware of rate limits (HTTP 429 Retry-After)."""
from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


class ProviderError(Exception):
    """A failure that retrying will not fix (bad request, auth, content filter)."""


class RetryableError(Exception):
    """A failure worth retrying (timeouts, 5xx, rate limits)."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def with_retries(
    fn: Callable[[int], T],
    *,
    attempts: int = 4,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    on_error: Callable[[int, Exception], None] | None = None,
) -> T:
    """Call fn(attempt) until it succeeds. fn receives the 1-based attempt number."""
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn(attempt)
        except ProviderError as e:
            if on_error:
                on_error(attempt, e)
            raise
        except (RetryableError, TimeoutError, ConnectionError) as e:
            last = e
            if on_error:
                on_error(attempt, e)
            if attempt == attempts:
                break
            wait = getattr(e, "retry_after", None) or min(max_delay, base_delay * 2 ** (attempt - 1))
            wait += random.uniform(0, 0.5)
            print(f"    retry {attempt}/{attempts - 1} in {wait:.1f}s: {e}")
            time.sleep(wait)
    assert last is not None
    raise last
