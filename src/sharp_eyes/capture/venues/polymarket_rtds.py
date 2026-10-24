"""Polymarket live-data websocket (RTDS): wallet-attributed fills as they happen.

``wss://ws-live-data.polymarket.com``, topic ``activity``, type ``trades``.
Public, no auth. Every message is an envelope
``{"topic", "type", "timestamp" (ms), "connection_id", "payload"}`` whose
payload is one fill in camelCase (``proxyWallet``, ``asset``, ``conditionId``,
``transactionHash``, ...). The subscription is unfiltered (all of Polymarket)
and the worker keeps only the markets in its catalog: a filter per event slug
would need a resubscribe on every catalog change, and the full stream is small.

The Data API ``/v2/trades`` poll keeps running beside it. It fills the gaps
while the socket is down or reconnecting, and it is the only source of maker
rows if the socket turns out to carry taker fills only. Both feeds key a fill
the same way (:func:`polymarket.trade_key`), so the store merges them.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from websockets.asyncio.client import ClientConnection, connect

from sharp_eyes.capture.records import TradeRecord
from sharp_eyes.capture.venues.polymarket import parse_trade, trade_key

log = logging.getLogger(__name__)

RTDS = "wss://ws-live-data.polymarket.com"
SUBSCRIBE = {"action": "subscribe", "subscriptions": [{"topic": "activity", "type": "trades"}]}
PING_SECONDS = 5.0  # The official client sends a text "ping" every 5 s
FLUSH_SECONDS = 1.0
MAX_BACKOFF = 30.0
STALL_SECONDS = 60.0  # All of Polymarket goes quiet this long only if the feed is stuck
SEGMENT = timedelta(seconds=60)
ORDINAL_TTL = 900.0  # Seconds to remember a fill for telling identical fills apart


def rtds_row(payload: dict[str, Any]) -> dict[str, Any] | None:
    """An RTDS trade payload in Data API v2 shape (snake_case), or None if unusable.

    Without a transaction hash the fill cannot be keyed like its Data API
    twin, so it is dropped and the poll picks it up instead.
    """
    tx = payload.get("transactionHash")
    ts = payload.get("timestamp")
    if not tx or not ts:
        return None
    try:
        seconds = int(float(ts))
    except (TypeError, ValueError):
        return None
    if seconds > 10**11:  # Milliseconds
        seconds //= 1000
    return {
        "proxy_wallet": payload.get("proxyWallet") or "",
        "side": payload.get("side"),
        "token_id": str(payload.get("asset") or ""),
        "condition_id": payload.get("conditionId") or "",
        "size": payload.get("size"),
        "price": payload.get("price"),
        "timestamp": seconds,
        "transaction_hash": tx,
        "event_slug": payload.get("eventSlug"),
        "slug": payload.get("slug"),
        "outcome": payload.get("outcome"),
        "outcome_index": payload.get("outcomeIndex"),
        "rtds": payload,
    }


class OrdinalTracker:
    """Gives identical fills ordinals 0, 1, ... as the Data API does per response.

    The socket delivers fills one by one, so identical rows are counted over a
    sliding window instead of within one response.
    """

    def __init__(self, ttl: float = ORDINAL_TTL) -> None:
        self.ttl = ttl
        self._seen: dict[str, tuple[int, float]] = {}

    def key(self, row: dict[str, Any], now: float | None = None) -> str:
        now = time.monotonic() if now is None else now
        if len(self._seen) > 10_000:
            self._seen = {k: v for k, v in self._seen.items() if now - v[1] < self.ttl}
        base = trade_key(row, 0)
        count, at = self._seen.get(base, (0, now))
        if now - at >= self.ttl:
            count = 0
        self._seen[base] = (count + 1, now)
        return trade_key(row, count)


@dataclass
class Session:
    """A stretch of one websocket connection, stored as an ``rtds`` row in
    ``poll_runs``: one row per minute while connected, and a failed row when
    it drops, so gaps in websocket coverage show up like failed polls."""

    started_at: datetime
    finished_at: datetime
    ok: bool = True
    messages: int = 0  # Everything received (all of Polymarket)
    kept: int = 0  # Fills in catalog markets, handed to the store
    error: str | None = None


class RtdsTradeStream:
    def __init__(self, url: str = RTDS, *, open_timeout: float = 15.0) -> None:
        self.url = url
        self.open_timeout = open_timeout
        self.ordinals = OrdinalTracker()

    def parse(self, message: str | bytes, observed_at: datetime) -> TradeRecord | None:
        try:
            body = json.loads(message)
        except (TypeError, ValueError):
            return None  # "pong" and other keep-alive text
        if not isinstance(body, dict) or body.get("topic") != "activity":
            return None
        if body.get("type") != "trades" or not isinstance(body.get("payload"), dict):
            return None
        row = rtds_row(body["payload"])
        if row is None:
            return None
        return parse_trade(self.ordinals.key(row), row, observed_at, None, None, source="ws")

    async def run(
        self,
        wanted: Callable[[TradeRecord], bool],
        on_trades: Callable[[list[TradeRecord]], Awaitable[None]],
        on_session: Callable[[Session], Awaitable[None]],
    ) -> None:
        """Stream forever: reconnect with backoff, flush kept fills every second."""
        backoff = 1.0
        while True:
            received = await self._connection(wanted, on_trades, on_session)
            if received:
                backoff = 1.0
            log.warning("RTDS disconnected; reconnecting in %.0f s", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

    async def _connection(
        self,
        wanted: Callable[[TradeRecord], bool],
        on_trades: Callable[[list[TradeRecord]], Awaitable[None]],
        on_session: Callable[[Session], Awaitable[None]],
    ) -> int:
        """One connection, until it drops or stalls. Returns messages received."""
        seg = Session(datetime.now(UTC), datetime.now(UTC))
        buffer: list[TradeRecord] = []
        received = 0

        async def flush() -> None:
            nonlocal buffer
            if buffer:
                batch, buffer = buffer, []
                seg.kept += len(batch)
                await on_trades(batch)

        try:
            async with connect(self.url, open_timeout=self.open_timeout) as ws:
                await ws.send(json.dumps(SUBSCRIBE))
                log.info("RTDS connected, subscribed to activity/trades")
                pinger = asyncio.create_task(_ping(ws))
                last_message = time.monotonic()
                try:
                    async for message, observed in _messages(ws, FLUSH_SECONDS):
                        now = time.monotonic()
                        if message is not None:
                            received += 1
                            seg.messages += 1
                            last_message = now
                            trade = self.parse(message, observed)
                            if trade is not None and wanted(trade):
                                buffer.append(trade)
                            if len(buffer) < 200:
                                continue
                        await flush()
                        if now - last_message > STALL_SECONDS:
                            raise TimeoutError(f"no message for {STALL_SECONDS:.0f} s")
                        if observed - seg.started_at >= SEGMENT:
                            seg.finished_at = observed
                            await on_session(seg)
                            seg = Session(observed, observed)
                finally:
                    pinger.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await pinger
        except Exception as exc:  # ConnectionClosed, DNS, TLS, handshake timeout, stall
            seg.ok = False
            seg.error = f"{type(exc).__name__}: {exc}"
        finally:
            await flush()
            seg.finished_at = datetime.now(UTC)
            await on_session(seg)
        return received


async def _ping(ws: ClientConnection) -> None:
    while True:
        await asyncio.sleep(PING_SECONDS)
        await ws.send("ping")


async def _messages(
    ws: ClientConnection, idle: float
) -> AsyncIterator[tuple[str | bytes | None, datetime]]:
    """Each message with its receive time; ``None`` after ``idle`` seconds of quiet
    (or every ``idle`` seconds under load) so the caller can flush."""
    deadline = time.monotonic() + idle
    while True:
        try:
            message = await asyncio.wait_for(ws.recv(), max(0.0, deadline - time.monotonic()))
        except TimeoutError:
            deadline = time.monotonic() + idle
            yield None, datetime.now(UTC)
            continue
        yield message, datetime.now(UTC)
        if time.monotonic() >= deadline:
            deadline = time.monotonic() + idle
            yield None, datetime.now(UTC)
