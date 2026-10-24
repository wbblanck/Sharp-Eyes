"""Store idempotency and the latency report, against a real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import Engine, func, select

from sharp_eyes.capture import schema as s
from sharp_eyes.capture.latency import build_report
from sharp_eyes.capture.records import (
    BetType,
    BookRef,
    BookSnapshot,
    CaptureVenue,
    EventRecord,
    MarketRecord,
    Period,
    TradeRecord,
)
from sharp_eyes.capture.store import CaptureStore
from sharp_eyes.capture.venues.base import Catalog

pytestmark = pytest.mark.db
NOW = datetime.now(UTC).replace(microsecond=0)


def catalog(status: str = "open", price: str = "0.5") -> Catalog:
    event = EventRecord(
        CaptureVenue.NOVIG, "e1", "NFL", "BAL @ BUF", NOW, "OPEN_PREGAME", {"id": "e1"}
    )
    market = MarketRecord(
        CaptureVenue.NOVIG, "m1", "e1", "MONEY", BetType.MONEYLINE, Period.FULL_GAME, None,
        "BUF", status, NOW, (BookRef("buf", "BUF"),), {"status": status, "bid": price},
    )  # fmt: skip
    return Catalog(events=[event], markets=[market])


def count(engine: Engine, table: object) -> int:
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(table)).scalar_one())  # type: ignore[arg-type]


def stable(raw: object) -> object:
    return {k: v for k, v in raw.items() if k != "bid"} if isinstance(raw, dict) else raw


def test_catalog_versions_only_on_stable_change(clean_engine: Engine) -> None:
    store = CaptureStore(clean_engine)
    assert store.upsert_catalog("NOVIG", catalog(), stable, NOW) == 2
    assert store.upsert_catalog("NOVIG", catalog(price="0.6"), stable, NOW) == 0  # price only
    assert store.upsert_catalog("NOVIG", catalog(status="closed"), stable, NOW) == 1
    assert count(clean_engine, s.catalog_versions) == 3
    with clean_engine.connect() as conn:
        assert conn.execute(select(s.markets.c.status)).scalar_one() == "closed"


def trade(key: str, taker: bool | None, prev: datetime | None = None, lag: int = 3) -> TradeRecord:
    ts = NOW - timedelta(seconds=10)
    return TradeRecord(
        CaptureVenue.POLYMARKET, key, "0xml", "111", ts, D("0.6"), D("5"), side="BUY",
        wallet="0xa", raw={"k": key}, seen_in_taker_feed=taker,
        observed_at=ts + timedelta(seconds=lag), prev_poll_at=prev,
    )  # fmt: skip


def test_trades_are_idempotent_and_taker_flag_upgrades(clean_engine: Engine) -> None:
    store = CaptureStore(clean_engine)
    assert store.insert_trades([trade("a", False), trade("b", False)]) == 2
    assert store.insert_trades([trade("a", True), trade("c", None)]) == 1
    with clean_engine.connect() as conn:
        flags = dict(
            conn.execute(select(s.trades.c.trade_key, s.trades.c.seen_in_taker_feed)).all()
        )
    assert flags == {"a": True, "b": False, "c": None}


def test_book_insert_and_latest_hashes(clean_engine: Engine) -> None:
    store = CaptureStore(clean_engine)
    snap = BookSnapshot(
        CaptureVenue.KALSHI, "T", "T", NOW, ((D("0.6"), D("5")),), ((D("0.61"), D("8")),)
    )
    store.insert_books([snap])
    assert store.latest_book_hashes("KALSHI") == {"T": snap.content_hash()}
    with clean_engine.connect() as conn:
        row = conn.execute(select(s.book_snapshots)).mappings().one()
    assert row["bids"] == [["0.6", "5"]] and row["best_ask"] == D("0.61")


def test_checkpoints_round_trip(clean_engine: Engine) -> None:
    store = CaptureStore(clean_engine)
    store.set_checkpoints("KALSHI", {"trades:global": "1"})
    store.set_checkpoints("KALSHI", {"trades:global": "2", "x": "y"})
    assert store.get_checkpoints("KALSHI") == {"trades:global": "2", "x": "y"}


def test_latency_report_brackets_visibility(clean_engine: Engine) -> None:
    store = CaptureStore(clean_engine)
    prev = NOW - timedelta(seconds=9)  # 1 s after the fill
    store.insert_trades(
        [trade(f"t{i}", False, prev=prev, lag=3 + i) for i in range(10)]
        + [trade("backfill", None, prev=None, lag=500)]
    )
    store.record_poll("POLYMARKET", "trades", NOW - timedelta(seconds=4), NOW, ok=True)
    store.record_poll("POLYMARKET", "trades", NOW - timedelta(seconds=2), NOW, ok=True)
    store.add_status_sample("POLYMARKET", NOW, D("1.5"), {"serving": {"lag_seconds": 1.5}})

    report = build_report(clean_engine, NOW - timedelta(hours=1), NOW + timedelta(hours=1))
    assert report.samples == 10  # The backfill row carries no sample
    assert report.upper["max"] == 12.0 and report.upper["p50"] == pytest.approx(7.5)
    assert report.lower["p50"] == pytest.approx(1.0)
    assert report.share_visible_within["10s"] == pytest.approx(0.8)
    assert report.trade_polls["polls"] == 2 and report.api_status_lag["p50"] == 1.5
    assert "detection latency" in report.to_markdown()


def sighting(key: str, source: str, lag: float, taker: bool | None = None) -> TradeRecord:
    ts = NOW - timedelta(seconds=60)
    prev = ts + timedelta(seconds=lag - 2) if source == "api" else None
    return TradeRecord(
        CaptureVenue.POLYMARKET, key, "0xml", "111", ts, D("0.6"), D("5"), side="BUY",
        wallet="0xa", raw={"k": key}, seen_in_taker_feed=taker,
        observed_at=ts + timedelta(seconds=lag), prev_poll_at=prev, source=source,
    )  # fmt: skip


def test_feeds_merge_into_one_row_with_both_sightings(clean_engine: Engine) -> None:
    store = CaptureStore(clean_engine)
    assert store.insert_trades([sighting("a", "ws", 0.5)]) == 1
    assert store.insert_trades([sighting("a", "api", 12, taker=True)]) == 0
    assert store.insert_trades([sighting("b", "api", 9, taker=False)]) == 1
    assert store.insert_trades([sighting("b", "ws", 0.4), sighting("a", "api", 30)]) == 0
    with clean_engine.connect() as conn:
        rows = {r["trade_key"]: r for r in conn.execute(select(s.trades)).mappings()}
    ts = NOW - timedelta(seconds=60)
    a, b = rows["a"], rows["b"]
    assert a["observed_at"] == a["ws_observed_at"] == ts + timedelta(seconds=0.5)
    assert a["api_observed_at"] == ts + timedelta(seconds=12)  # First poll only
    assert a["prev_poll_at"] == ts + timedelta(seconds=10) and a["seen_in_taker_feed"] is True
    assert b["observed_at"] == b["ws_observed_at"] == ts + timedelta(seconds=0.4)
    assert b["api_observed_at"] == ts + timedelta(seconds=9) and b["seen_in_taker_feed"] is False


def test_latency_report_compares_websocket_and_poll(clean_engine: Engine) -> None:
    store = CaptureStore(clean_engine)
    store.insert_trades([sighting(f"t{i}", "ws", 0.5 + i / 10) for i in range(4)])
    store.insert_trades(
        [sighting(f"t{i}", "api", 10 + i, taker=True) for i in range(3)]
        + [sighting("maker", "api", 10, taker=False)]
    )
    store.record_poll("POLYMARKET", "rtds", NOW - timedelta(minutes=2), NOW, ok=True, items=50)
    store.record_poll("POLYMARKET", "rtds", NOW, NOW, ok=False, error="ConnectionClosed")

    report = build_report(clean_engine, NOW - timedelta(hours=1), NOW + timedelta(hours=1))
    r = report.rtds
    assert r["samples"] == 4 and r["drops"] == 1 and r["connected_minutes"] == 2.0
    assert r["latency"]["max"] == pytest.approx(0.8)
    assert r["head_to_head"]["p50"] == pytest.approx(10.4)  # 10..12 s minus 0.5..0.7 s
    assert r["ws_first"] == 1.0
    assert r["coverage"] == {
        "both": 3, "ws_only": 1, "api_only": 1, "api_only_taker": 0, "api_only_maker": 1
    }  # fmt: skip
    assert report.samples == 4  # The poll's own bracket still uses its first sighting
    assert "Live-data websocket" in report.to_markdown()
