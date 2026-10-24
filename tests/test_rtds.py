"""Polymarket live-data websocket: parsing, keys that match the Data API, the stream."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal as D
from typing import Any

from websockets.asyncio.server import ServerConnection, serve

from sharp_eyes.capture.records import TradeRecord
from sharp_eyes.capture.venues import polymarket, polymarket_rtds
from sharp_eyes.capture.venues.polymarket_rtds import OrdinalTracker, RtdsTradeStream, Session

NOW = datetime(2026, 10, 25, 17, 0, tzinfo=UTC)


def payload(**over: Any) -> dict[str, Any]:
    body = {
        "asset": "111",
        "conditionId": "0xml",
        "eventSlug": "nfl-pit-no-2026-10-25",
        "slug": "nfl-pit-no-2026-10-25",
        "outcome": "Steelers",
        "outcomeIndex": 0,
        "price": 0.6,
        "proxyWallet": "0xAbC",
        "side": "BUY",
        "size": 200,
        "timestamp": 1792860236,
        "transactionHash": "0xTX",
        "name": "someone",
    }
    return {**body, **over}


def envelope(p: dict[str, Any], topic: str = "activity", kind: str = "trades") -> str:
    return json.dumps(
        {
            "topic": topic,
            "type": kind,
            "timestamp": 1792860236512,
            "payload": p,
            "connection_id": "c",
        }
    )


def api_row() -> dict[str, Any]:
    """The same fill as :func:`payload`, as Data API v2 returns it."""
    return {
        "proxy_wallet": "0xabc",
        "side": "BUY",
        "token_id": "111",
        "condition_id": "0xml",
        "size": 200.0,
        "price": 0.6,
        "timestamp": 1792860236,
        "transaction_hash": "0xtx",
    }


def test_websocket_fill_keys_like_its_data_api_twin() -> None:
    trade = RtdsTradeStream().parse(envelope(payload()), NOW)
    assert trade is not None and trade.source == "ws"
    assert trade.trade_key == polymarket.keyed_rows([api_row()])[0][0]
    assert trade.wallet == "0xabc" and trade.size == D("200") and trade.price == D("0.6")
    assert trade.ts == datetime(2026, 10, 24, 16, 43, 56, tzinfo=UTC)
    assert trade.raw["rtds"]["name"] == "someone"


def test_parse_skips_keepalives_other_topics_and_unkeyable_fills() -> None:
    stream = RtdsTradeStream()
    assert stream.parse("pong", NOW) is None
    assert stream.parse("", NOW) is None
    assert stream.parse(envelope(payload(), topic="comments"), NOW) is None
    assert stream.parse(envelope(payload(), kind="orders_matched"), NOW) is None
    assert stream.parse(envelope(payload(transactionHash="")), NOW) is None


def test_millisecond_timestamps_are_read_as_seconds() -> None:
    row = polymarket_rtds.rtds_row(payload(timestamp=1792860236512))
    assert row is not None and row["timestamp"] == 1792860236


def test_identical_fills_get_ordinals_until_they_expire() -> None:
    tracker = OrdinalTracker(ttl=60)
    row = api_row()
    assert tracker.key(row, now=0).endswith("|0")
    assert tracker.key(row, now=1).endswith("|1")
    assert tracker.key({**row, "proxy_wallet": "0xdef"}, now=2).endswith("|0")
    assert tracker.key(row, now=100).endswith("|0")


async def test_stream_keeps_wanted_fills_and_records_drops() -> None:
    sent = [
        envelope(payload()),
        "pong",
        envelope(payload(conditionId="0xother", transactionHash="0xtx2")),
        envelope(payload(transactionHash="0xtx3", size=5)),
    ]
    subscriptions: list[Any] = []

    async def handler(ws: ServerConnection) -> None:
        subscriptions.append(json.loads(await ws.recv()))
        for message in sent:
            await ws.send(message)
        await ws.close()  # The client must notice, record it and reconnect

    got: list[TradeRecord] = []
    sessions: list[Session] = []

    async def on_trades(trades: list[TradeRecord]) -> None:
        got.extend(trades)

    async def on_session(seg: Session) -> None:
        sessions.append(seg)

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        stream = RtdsTradeStream(f"ws://127.0.0.1:{port}")
        task = asyncio.create_task(
            stream.run(lambda t: t.market_id == "0xml", on_trades, on_session)
        )
        for _ in range(100):
            if len(sessions) >= 2:
                break
            await asyncio.sleep(0.05)
        task.cancel()

    assert subscriptions[0] == polymarket_rtds.SUBSCRIBE
    assert [t.tx_hash for t in got[:2]] == ["0xTX", "0xtx3"]
    assert all(t.source == "ws" and t.observed_at is not None for t in got)
    assert not sessions[0].ok and sessions[0].messages == 4 and sessions[0].kept == 2


async def test_worker_stores_websocket_fills_for_catalog_markets_only() -> None:
    from sharp_eyes.capture.records import BetType, MarketRecord, Period
    from sharp_eyes.capture.records import CaptureVenue as V
    from sharp_eyes.capture.worker import build_runners
    from sharp_eyes.config import AppConfig

    class Store:
        def __init__(self) -> None:
            self.trades: list[TradeRecord] = []
            self.polls: list[tuple[str, bool]] = []

        def insert_trades(self, trades: list[TradeRecord]) -> int:
            self.trades.extend(trades)
            return len(trades)

        def record_poll(self, venue: str, job: str, *a: Any, ok: bool, **k: Any) -> None:
            self.polls.append((job, ok))

    class Stream(RtdsTradeStream):
        async def run(self, wanted, on_trades, on_session) -> None:  # type: ignore[no-untyped-def]
            fills = [self.parse(envelope(payload(conditionId=c)), NOW) for c in ("0xml", "0xno")]
            await on_trades([t for t in fills if t is not None and wanted(t)])
            await on_session(Session(NOW, NOW, ok=False, error="closed"))
            raise asyncio.CancelledError

    store = Store()
    runner = build_runners(AppConfig(), store)[0]  # type: ignore[arg-type]
    runner.markets = {
        "0xml": MarketRecord(
            V.POLYMARKET,
            "0xml",
            "e1",
            "moneyline",
            BetType.MONEYLINE,
            Period.FULL_GAME,
            None,
            "PIT @ NO",
            "open",
            NOW,
            (),
            {},
        )  # fmt: skip
    }
    runner.catalog_ready.set()
    try:
        await runner.rtds_loop(Stream())  # type: ignore[attr-defined]
    except asyncio.CancelledError:
        pass
    assert [t.market_id for t in store.trades] == ["0xml"]
    assert store.polls == [("rtds", False)]
