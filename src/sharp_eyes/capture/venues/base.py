"""Shared adapter plumbing."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, TypeVar

from sharp_eyes.capture.http import VenueHttp
from sharp_eyes.capture.records import (
    BetType,
    BookSnapshot,
    CaptureVenue,
    EventRecord,
    MarketRecord,
    Period,
    TradeRecord,
)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class Catalog:
    events: list[EventRecord] = field(default_factory=list)
    markets: list[MarketRecord] = field(default_factory=list)


@dataclass
class TradeBatch:
    trades: list[TradeRecord]
    # Updated checkpoint values (stream key -> value) to persist with the batch.
    checkpoints: dict[str, str] = field(default_factory=dict)


class VenueAdapter(ABC):
    venue: CaptureVenue
    # Volatile fields stripped before hashing a catalog object, so a moving
    # price or volume does not create a new catalog version every refresh.
    volatile_keys: frozenset[str] = frozenset()

    def __init__(self, http: VenueHttp, *, max_levels: int = 50, concurrency: int = 4) -> None:
        self.http = http
        self.max_levels = max_levels
        self.concurrency = concurrency

    @abstractmethod
    async def fetch_catalog(self, window_start: datetime, window_end: datetime) -> Catalog:
        """NFL events starting inside the window, with their markets."""

    @abstractmethod
    async def fetch_books(self, markets: Sequence[MarketRecord]) -> list[BookSnapshot]:
        """Current books for the given markets."""

    @abstractmethod
    async def fetch_trades(
        self, markets: Sequence[MarketRecord], checkpoints: dict[str, str]
    ) -> TradeBatch:
        """Trades since the stored checkpoints, for the given markets."""

    def request_count(self) -> int:
        return self.http.requests

    def stable_view(self, raw: Any) -> Any:
        return strip_keys(raw, self.volatile_keys)

    async def aclose(self) -> None:
        await self.http.aclose()


def strip_keys(raw: Any, keys: frozenset[str]) -> Any:
    if isinstance(raw, dict):
        return {k: strip_keys(v, keys) for k, v in raw.items() if k not in keys}
    if isinstance(raw, list):
        return [strip_keys(v, keys) for v in raw]
    return raw


def chunks(items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace(" ", "T", 1)
    if text.endswith("+00"):
        text += ":00"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def from_epoch(value: int | float, *, millis: bool = False) -> datetime:
    return datetime.fromtimestamp(value / 1000 if millis else value, UTC)


def classify(mapping: dict[str, tuple[BetType, Period]], key: str) -> tuple[BetType, Period]:
    return mapping.get(key, (BetType.OTHER, Period.OTHER))


def in_window(start: datetime | None, window_start: datetime, window_end: datetime) -> bool:
    return start is not None and window_start <= start <= window_end


def unique(items: Iterable[T]) -> list[T]:
    return list(dict.fromkeys(items))


async def gather_limited(
    items: Sequence[T], fn: Callable[[T], Awaitable[R]], limit: int
) -> list[R | BaseException]:
    """Run ``fn`` over ``items`` with at most ``limit`` in flight; keeps order.

    Exceptions are returned in place so one failed book does not lose the rest.
    """
    sem = asyncio.Semaphore(limit)

    async def run(item: T) -> R:
        async with sem:
            return await fn(item)

    return list(await asyncio.gather(*(run(i) for i in items), return_exceptions=True))


def collect(
    results: Sequence[R | None | BaseException], log: logging.Logger, venue: str
) -> list[R]:
    """Keep successful results; log failures (the next cycle retries them)."""
    out: list[R] = []
    errors = [r for r in results if isinstance(r, BaseException)]
    for r in results:
        if r is not None and not isinstance(r, BaseException):
            out.append(r)
    if errors:
        log.warning(
            "%s: %d of %d requests failed, first: %s", venue, len(errors), len(results), errors[0]
        )
    return out
