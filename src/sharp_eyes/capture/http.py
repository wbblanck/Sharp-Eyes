"""Rate-limited, retrying HTTP client shared by the venue adapters.

Each venue gets its own :class:`VenueHttp` with its own token bucket, so one
venue backing off never slows the others. Retries cover 429 and transient 5xx
and network errors. ``Retry-After`` is honoured when sent (Polymarket, Novig);
Kalshi sends 429 without it, so we fall back to exponential backoff with jitter.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

USER_AGENT = "sharp-eyes-capture/0.1 (+https://github.com/wbblanck/Sharp-Eyes)"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class TokenBucket:
    """Async token bucket: ``rate`` tokens per second, bursting up to ``burst``."""

    def __init__(self, rate: float, burst: int | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.rate = rate
        self.capacity = float(burst if burst is not None else max(1, int(rate)))
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
                self._updated = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await asyncio.sleep((1 - self._tokens) / self.rate)

    def penalize(self, seconds: float) -> None:
        """Drain the bucket so the next request waits at least ``seconds``."""
        self._tokens = min(self._tokens, -seconds * self.rate)
        self._updated = time.monotonic()


class VenueHttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Response:
    status: int
    data: Any
    headers: httpx.Headers
    elapsed_ms: int


def retry_delay(
    attempt: int, retry_after: str | None, base: float = 0.5, cap: float = 30.0
) -> float:
    """Seconds to wait before retry ``attempt`` (1-based)."""
    if retry_after:
        try:
            return min(cap, max(0.0, float(retry_after)))
        except ValueError:
            pass  # HTTP-date form; nobody we call sends it, fall through to backoff
    exp: float = min(cap, base * (2 ** (attempt - 1)))
    return float(exp * (0.5 + random.random() / 2))  # noqa: S311 - jitter, not crypto


class VenueHttp:
    def __init__(
        self,
        venue: str,
        base_url: str,
        *,
        rate_per_second: float,
        burst: int | None = None,
        max_attempts: int = 5,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.venue = venue
        self.bucket = TokenBucket(rate_per_second, burst)
        self.max_attempts = max_attempts
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            transport=transport,
        )
        self.requests = 0
        self.retries = 0

    async def aclose(self) -> None:
        await self.client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        ok_statuses: frozenset[int] = frozenset({200}),
    ) -> Response:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            await self.bucket.acquire()
            self.requests += 1
            started = time.monotonic()
            try:
                resp = await self.client.request(
                    method, path, params=params, json=json, headers=headers
                )
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                delay = retry_delay(attempt, None)
            else:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                if resp.status_code in ok_statuses:
                    data = resp.json() if resp.content and resp.status_code != 304 else None
                    return Response(resp.status_code, data, resp.headers, elapsed_ms)
                last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                if resp.status_code not in RETRY_STATUSES:
                    raise VenueHttpError(
                        f"{self.venue} {method} {path} failed: {last_error}", resp.status_code
                    )
                delay = retry_delay(attempt, resp.headers.get("Retry-After"))
                if resp.status_code == 429:
                    self.bucket.penalize(delay)
            if attempt < self.max_attempts:
                self.retries += 1
                log.debug(
                    "%s %s %s retry %d in %.1fs: %s",
                    self.venue,
                    method,
                    path,
                    attempt,
                    delay,
                    last_error,
                )
                await asyncio.sleep(delay)
        raise VenueHttpError(f"{self.venue} {method} {path} gave up: {last_error}")

    async def get(self, path: str, **kwargs: Any) -> Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Response:
        return await self.request("POST", path, **kwargs)
