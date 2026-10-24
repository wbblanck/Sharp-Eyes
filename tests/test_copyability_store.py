from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine

from sharp_eyes.capture.records import CaptureVenue
from sharp_eyes.capture.schema import book_snapshots, poll_runs, trades
from sharp_eyes.config import load_config
from sharp_eyes.copyability.store import CaptureQuotes, load_source_fills

pytestmark = pytest.mark.db

KX = CaptureVenue.KALSHI
KICKOFF = datetime(2026, 10, 25, 17, 0, tzinfo=UTC)
KEY = "KXNFLGAME-26OCT25PITNO-NO"


def _snapshot(at: datetime, ask: str) -> dict[str, object]:
    return {
        "venue": KX.value,
        "market_id": KEY,
        "book_key": KEY,
        "observed_at": at,
        "bids": [["0.40", "10"]],
        "asks": [[ask, "10"]],
        "content_hash": ask,
    }


def _poll(at: datetime, ok: bool = True) -> dict[str, object]:
    return {"venue": KX.value, "job": "books", "started_at": at, "finished_at": at, "ok": ok}


def test_book_at_requires_continuous_polling(clean_engine: Engine) -> None:
    config = load_config()
    quotes = CaptureQuotes(clean_engine, config.capture)
    t0 = KICKOFF - timedelta(hours=2)  # Inside the 3 h tier
    interval = config.capture.books_interval(120)
    with clean_engine.begin() as conn:
        conn.execute(
            book_snapshots.insert(),
            [_snapshot(t0, "0.42"), _snapshot(t0 + timedelta(minutes=5), "0.44")],
        )
        conn.execute(
            poll_runs.insert(),
            [_poll(t0 + timedelta(seconds=s)) for s in range(0, 600, interval)],
        )

    # Latest stored book at or before the follow time, unchanged since.
    looked = quotes.book_at(KX, KEY, t0 + timedelta(minutes=3), KICKOFF)
    assert looked.book is not None and str(looked.book.asks[0][0]) == "0.42"
    assert looked.age_bound_seconds == interval
    later = quotes.book_at(KX, KEY, t0 + timedelta(minutes=7), KICKOFF)
    assert later.book is not None and str(later.book.asks[0][0]) == "0.44"

    # Polling stopped at t0 + 10 min: a book after that is unknown, not "unchanged".
    gap = quotes.book_at(KX, KEY, t0 + timedelta(minutes=20), KICKOFF)
    assert gap.book is None and "no KALSHI book poll" in (gap.problem or "")
    before = quotes.book_at(KX, KEY, t0 - timedelta(minutes=1), KICKOFF)
    assert before.book is None and "never captured" in (before.problem or "")

    with clean_engine.begin() as conn:
        conn.execute(poll_runs.insert(), [_poll(t0 + timedelta(minutes=3, seconds=-1), ok=False)])
    failed = quotes.book_at(KX, KEY, t0 + timedelta(minutes=3), KICKOFF)
    assert failed.book is None and "failed" in (failed.problem or "")

    # The closing book needs a poll in the last ten minutes before kickoff.
    assert quotes.closing_book(KX, KEY, KICKOFF) is None
    with clean_engine.begin() as conn:
        conn.execute(poll_runs.insert(), [_poll(KICKOFF - timedelta(minutes=1))])
    close = quotes.closing_book(KX, KEY, KICKOFF)
    assert close is not None and str(close.asks[0][0]) == "0.44"


def test_backfilled_fills_are_excluded(clean_engine: Engine) -> None:
    ts = KICKOFF - timedelta(hours=1)
    row = {
        "venue": "POLYMARKET",
        "market_id": "m1",
        "book_key": "tok",
        "ts": ts,
        "observed_at": ts + timedelta(seconds=20),
        "price": "0.40",
        "size": "100",
        "side": "BUY",
        "wallet": "0xabc",
        "raw": {},
    }
    with clean_engine.begin() as conn:
        conn.execute(
            trades.insert(),
            [
                {**row, "trade_key": "live", "prev_poll_at": ts},
                {**row, "trade_key": "backfill", "prev_poll_at": None},
            ],
        )
    fills, backfilled = load_source_fills(
        clean_engine, ts - timedelta(hours=1), ts + timedelta(hours=1)
    )
    assert backfilled == 1 and len(fills) == 1 and fills[0].side == "BUY"
