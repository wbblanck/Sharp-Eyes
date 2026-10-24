"""Reads the Phase 0 capture tables for copyability scoring.

Books are stored only when they change, so "the book at time t" is the latest
stored snapshot at or before t, and it is only trustworthy if the worker kept
polling that venue's books up to t. ``CaptureQuotes`` checks that against
``poll_runs`` and reports a problem instead of returning a stale book.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, text

from sharp_eyes.capture.records import (
    BetType,
    BookRef,
    CaptureVenue,
    EventRecord,
    Level,
    MarketRecord,
    Period,
)
from sharp_eyes.capture.schema import SCHEMA
from sharp_eyes.config import CaptureConfig
from sharp_eyes.copyability.score import BookLookup, BookView
from sharp_eyes.copyability.wagers import SourceFill

# How close to kickoff a closing book must have been confirmed by a poll.
CLOSE_CONFIRM = timedelta(minutes=10)


def _levels(raw: Iterable[Any]) -> tuple[Level, ...]:
    return tuple((Decimal(str(p)), Decimal(str(q))) for p, q in raw)


class CaptureQuotes:
    """``QuoteSource`` over ``capture.book_snapshots`` and ``capture.poll_runs``."""

    def __init__(self, engine: Engine, capture: CaptureConfig) -> None:
        self.engine = engine
        self.capture = capture

    def _snapshot(
        self, venue: CaptureVenue, book_key: str, before: datetime, *, strict: bool = False
    ) -> BookView | None:
        op = "<" if strict else "<="
        sql = text(
            f"SELECT bids, asks, observed_at FROM {SCHEMA}.book_snapshots "
            f"WHERE venue = :venue AND book_key = :key AND observed_at {op} :at "
            "ORDER BY observed_at DESC LIMIT 1"
        )
        with self.engine.connect() as conn:
            row = conn.execute(sql, {"venue": venue.value, "key": book_key, "at": before}).first()
        if row is None:
            return None
        return BookView(_levels(row.bids), _levels(row.asks), row.observed_at)

    def _polls(self, venue: CaptureVenue, start: datetime, end: datetime) -> tuple[int, int]:
        sql = text(
            f"SELECT count(*) FILTER (WHERE ok), count(*) FILTER (WHERE NOT ok) "
            f"FROM {SCHEMA}.poll_runs WHERE venue = :venue AND job = 'books' "
            "AND started_at > :start AND started_at <= :end"
        )
        with self.engine.connect() as conn:
            ok, failed = conn.execute(sql, {"venue": venue.value, "start": start, "end": end}).one()
        return int(ok or 0), int(failed or 0)

    def book_at(
        self, venue: CaptureVenue, book_key: str, at: datetime, kickoff: datetime | None
    ) -> BookLookup:
        minutes = (kickoff - at).total_seconds() / 60 if kickoff else float("inf")
        interval = self.capture.books_interval(minutes)
        book = self._snapshot(venue, book_key, at)
        if book is None:
            return BookLookup(None, "book never captured before the follow time", interval)
        # The worker polls each book once per tier interval. It must have run
        # in the last two intervals, without a failed sweep in the last one.
        ok, _ = self._polls(venue, at - timedelta(seconds=2 * interval), at)
        _, failed = self._polls(venue, at - timedelta(seconds=interval), at)
        if not ok:
            problem = f"no {venue.value} book poll in the {2 * interval} s before"
            return BookLookup(None, problem, interval)
        if failed:
            return BookLookup(None, f"{venue.value} book poll failed just before", interval)
        return BookLookup(book, None, interval)

    def closing_book(
        self, venue: CaptureVenue, book_key: str, kickoff: datetime
    ) -> BookView | None:
        book = self._snapshot(venue, book_key, kickoff, strict=True)
        if book is None:
            return None
        ok, _ = self._polls(venue, kickoff - CLOSE_CONFIRM, kickoff)
        return book if ok else None


def load_catalog(
    engine: Engine, start: datetime, end: datetime
) -> tuple[list[EventRecord], list[MarketRecord]]:
    """Events and core-period markets whose games start inside [start, end]."""
    with engine.connect() as conn:
        ev_rows = conn.execute(
            text(
                f"SELECT venue, event_id, league, title, start_time, status, raw "
                f"FROM {SCHEMA}.events WHERE start_time BETWEEN :s AND :e"
            ),
            {"s": start - timedelta(days=1), "e": end + timedelta(days=1)},
        ).all()
        mk_rows = conn.execute(
            text(
                f"SELECT venue, market_id, event_id, venue_market_type, bet_type, period, line, "
                f"title, status, start_time, books, raw FROM {SCHEMA}.markets "
                "WHERE start_time BETWEEN :s AND :e AND period = 'FULL_GAME' "
                "AND bet_type IN ('MONEYLINE', 'SPREAD', 'TOTAL')"
            ),
            {"s": start, "e": end},
        ).all()
    events = [
        EventRecord(
            CaptureVenue(r.venue), r.event_id, r.league, r.title, r.start_time, r.status, r.raw
        )  # fmt: skip
        for r in ev_rows
    ]
    markets = [
        MarketRecord(
            venue=CaptureVenue(r.venue),
            market_id=r.market_id,
            event_id=r.event_id,
            venue_market_type=r.venue_market_type,
            bet_type=BetType(r.bet_type),
            period=Period(r.period),
            line=r.line,
            title=r.title,
            status=r.status,
            start_time=r.start_time,
            books=tuple(BookRef(b["book_key"], b["outcome"]) for b in r.books),
            raw=r.raw,
        )
        for r in mk_rows
    ]
    return events, markets


def load_source_fills(
    engine: Engine, start: datetime, end: datetime
) -> tuple[list[SourceFill], int]:
    """Live-detected Polymarket fills with block time in [start, end].

    Backfilled rows (no ``prev_poll_at``) are excluded: their observation time
    says when we backfilled, not when a follower could have seen them. The
    second value counts them.
    """
    sql = text(
        f"SELECT wallet, market_id, book_key, side, price, size, ts, observed_at, "
        f"seen_in_taker_feed, prev_poll_at IS NOT NULL AS live FROM {SCHEMA}.trades "
        "WHERE venue = 'POLYMARKET' AND wallet IS NOT NULL AND ts BETWEEN :s AND :e"
    )
    fills, backfilled = [], 0
    with engine.connect() as conn:
        for r in conn.execute(sql, {"s": start, "e": end}):
            if not r.live:
                backfilled += 1
                continue
            fills.append(
                SourceFill(
                    r.wallet,
                    r.market_id,
                    r.book_key,
                    (r.side or "").upper(),
                    r.price,
                    r.size,
                    r.ts,
                    r.observed_at,
                    r.seen_in_taker_feed,
                )  # fmt: skip
            )
    return fills, backfilled
