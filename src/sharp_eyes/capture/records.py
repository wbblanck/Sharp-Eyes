"""Venue-neutral records produced by the capture adapters.

Units are normalised so that downstream code never has to know the venue:

* Prices are probabilities in [0, 1] as ``Decimal``.
* Sizes are counted in **$1-payout contracts**: Polymarket shares, Polymarket US
  and Kalshi contracts pay $1; a Novig contract pays 1 cent, so Novig
  quantities are divided by 100. The untouched venue payload is always kept.
* Book levels are best-first: bids descending, asks ascending.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

Level = tuple[Decimal, Decimal]  # (price, size)


class CaptureVenue(StrEnum):
    POLYMARKET = "POLYMARKET"
    POLYMARKET_US = "POLYMARKET_US"
    KALSHI = "KALSHI"
    NOVIG = "NOVIG"


class BetType(StrEnum):
    """Coarse bet-type axis (audit recommendation 7: bet type x period)."""

    MONEYLINE = "MONEYLINE"
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    TEAM_TOTAL = "TEAM_TOTAL"
    PROP = "PROP"
    OTHER = "OTHER"


class Period(StrEnum):
    FULL_GAME = "FULL_GAME"
    FIRST_HALF = "1H"
    SECOND_HALF = "2H"
    Q1 = "1Q"
    Q2 = "2Q"
    Q3 = "3Q"
    Q4 = "4Q"
    OTHER = "OTHER"


CORE_BET_TYPES = frozenset({BetType.MONEYLINE, BetType.SPREAD, BetType.TOTAL})


@dataclass(frozen=True)
class EventRecord:
    venue: CaptureVenue
    event_id: str
    league: str
    title: str
    start_time: datetime | None
    status: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class BookRef:
    """One order book to poll. ``book_key`` is what the venue's book API takes."""

    book_key: str
    outcome: str


@dataclass(frozen=True)
class MarketRecord:
    venue: CaptureVenue
    market_id: str
    event_id: str
    venue_market_type: str
    bet_type: BetType
    period: Period
    line: Decimal | None
    title: str
    status: str
    start_time: datetime | None
    books: tuple[BookRef, ...]
    raw: dict[str, Any]

    @property
    def is_core(self) -> bool:
        return self.bet_type in CORE_BET_TYPES and self.period is Period.FULL_GAME


@dataclass(frozen=True)
class BookSnapshot:
    venue: CaptureVenue
    market_id: str
    book_key: str
    observed_at: datetime  # Our receive time (UTC); the only time every venue supports
    bids: tuple[Level, ...]
    asks: tuple[Level, ...]
    venue_ts: datetime | None = None
    seq: int | None = None
    extra: dict[str, Any] | None = None  # e.g. Polymarket US market stats
    request_ms: int | None = None

    @property
    def best_bid(self) -> Decimal | None:
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.asks[0][0] if self.asks else None

    def content_hash(self) -> str:
        """Hash of the book content only, so an unchanged book is stored once."""
        payload = {
            "b": [[str(p), str(s)] for p, s in self.bids],
            "a": [[str(p), str(s)] for p, s in self.asks],
        }
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()[:32]


@dataclass(frozen=True)
class TradeRecord:
    venue: CaptureVenue
    trade_key: str  # Native id, or a documented composite key (Polymarket)
    market_id: str
    book_key: str
    ts: datetime  # Venue time: block time (Polymarket, 1 s), match time elsewhere
    price: Decimal
    size: Decimal
    side: str | None = None  # Wallet perspective BUY/SELL (Polymarket only)
    taker_side: str | None = None  # Taker's outcome side where the venue reports it
    wallet: str | None = None  # Polymarket proxy wallet; None on anonymous venues
    tx_hash: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    seen_in_taker_feed: bool | None = None
    observed_at: datetime | None = None  # When our response carrying it arrived
    # Start of the previous poll of the same scope, which did not return this
    # trade. With observed_at it brackets when the trade became visible in the
    # API. None for backfill or the first poll of a scope (no latency sample).
    prev_poll_at: datetime | None = None
    # Which feed delivered this row: "api" (REST polls, backfill) or "ws"
    # (Polymarket's live-data websocket). The store keeps each feed's first
    # sighting so the two can be compared fill by fill.
    source: str = "api"


def content_hash(raw: Any) -> str:
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()[:32]


def aggregate_levels(
    levels: Iterable[tuple[Decimal, Decimal]], *, descending: bool, max_levels: int
) -> tuple[Level, ...]:
    """Sum sizes per price, drop empty levels, sort best-first and truncate."""
    totals: dict[Decimal, Decimal] = {}
    for price, size in levels:
        if size > 0:
            totals[price] = totals.get(price, Decimal(0)) + size
    ordered = sorted(totals.items(), key=lambda kv: kv[0], reverse=descending)
    return tuple(ordered[:max_levels])


def complement(levels: Sequence[Level]) -> tuple[Level, ...]:
    """Bids on the opposite outcome at p are asks on this outcome at 1 - p."""
    return tuple((Decimal(1) - p, s) for p, s in levels)
