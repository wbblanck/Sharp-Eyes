"""International Polymarket: Gamma catalog, CLOB books, Data API v2 trades.

This is the signal source (the only venue that attributes trades to wallets).
Data API v1 retired on 2026-10-24, so only ``/v2`` routes are used.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from sharp_eyes.capture.http import VenueHttp
from sharp_eyes.capture.records import (
    BetType,
    BookRef,
    BookSnapshot,
    CaptureVenue,
    EventRecord,
    MarketRecord,
    Period,
    TradeRecord,
    aggregate_levels,
)
from sharp_eyes.capture.venues.base import (
    Catalog,
    TradeBatch,
    VenueAdapter,
    chunks,
    classify,
    dec,
    from_epoch,
    in_window,
    parse_iso,
)

log = logging.getLogger(__name__)

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DATA = "https://data-api.polymarket.com"

NFL_SERIES_ID = "12185"  # Gamma sports metadata: nfl -> series 12185 (NFL 2026)
BOOKS_PER_REQUEST = 500  # CLOB POST /books rejects more ("Payload exceeds the limit")
EVENTS_PER_TRADE_QUERY = 20  # /v2/trades event_id accepts at most 20 ids
TRADE_PAGE = 1000

_B, _P = BetType, Period
MARKET_TYPES: dict[str, tuple[BetType, Period]] = {
    "moneyline": (_B.MONEYLINE, _P.FULL_GAME),
    "spreads": (_B.SPREAD, _P.FULL_GAME),
    "totals": (_B.TOTAL, _P.FULL_GAME),
    "team_totals": (_B.TEAM_TOTAL, _P.FULL_GAME),
    "first_half_moneyline": (_B.MONEYLINE, _P.FIRST_HALF),
    "first_half_spreads": (_B.SPREAD, _P.FIRST_HALF),
    "first_half_totals": (_B.TOTAL, _P.FIRST_HALF),
    "first_half_team_totals": (_B.TEAM_TOTAL, _P.FIRST_HALF),
    "second_half_moneyline": (_B.MONEYLINE, _P.SECOND_HALF),
    "second_half_spreads": (_B.SPREAD, _P.SECOND_HALF),
    "second_half_totals": (_B.TOTAL, _P.SECOND_HALF),
    "second_half_team_totals": (_B.TEAM_TOTAL, _P.SECOND_HALF),
    **{f"q{n}_moneyline": (_B.MONEYLINE, Period(f"{n}Q")) for n in range(1, 5)},
    **{f"q{n}_spreads": (_B.SPREAD, Period(f"{n}Q")) for n in range(1, 5)},
    **{f"q{n}_totals": (_B.TOTAL, Period(f"{n}Q")) for n in range(1, 5)},
}


def _num(value: Any) -> str:
    """Canonical text for a price or size, so ``200``, ``200.0`` and ``"200"`` match."""
    d = dec(value)
    return "" if d is None else format(d.normalize(), "f")


def trade_key(row: dict[str, Any], ordinal: int) -> str:
    """Composite key: the Data API has no native trade id.

    ``transaction_hash`` alone is not unique (one transaction settles several
    fills, and the maker rows share it). Identical rows inside one response
    (same tx, wallet, token, side, price, size) are told apart by ``ordinal``.
    The block time is left out (the transaction fixes it) and numbers are
    canonicalised, so the websocket and the Data API key the same fill alike.
    """
    parts = [
        (row.get("transaction_hash") or "").lower(),
        str(row.get("token_id", "")),
        (row.get("proxy_wallet") or "").lower(),
        str(row.get("side", "")).upper(),
        _num(row.get("price")),
        _num(row.get("size")),
        str(ordinal),
    ]
    return "|".join(parts)


def keyed_rows(rows: Sequence[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    seen: Counter[str] = Counter()
    out = []
    for row in rows:
        base = trade_key(row, 0)
        out.append((trade_key(row, seen[base]), row))
        seen[base] += 1
    return out


def parse_event(raw: dict[str, Any]) -> tuple[EventRecord, list[MarketRecord]]:
    start = parse_iso(raw.get("startTime")) or parse_iso(raw.get("endDate"))
    if raw.get("closed"):
        status = "closed"
    elif raw.get("ended"):
        status = "ended"
    elif raw.get("live"):
        status = "live"
    else:
        status = "open"
    event = EventRecord(
        venue=CaptureVenue.POLYMARKET,
        event_id=str(raw["id"]),
        league="NFL",
        title=raw.get("title") or raw.get("slug") or "",
        start_time=start,
        status=status,
        raw={k: v for k, v in raw.items() if k != "markets"},
    )
    markets = []
    for m in raw.get("markets") or []:
        try:
            tokens = json.loads(m.get("clobTokenIds") or "[]")
            outcomes = json.loads(m.get("outcomes") or "[]")
        except (TypeError, ValueError):
            continue
        smt = m.get("sportsMarketType") or ""
        bet_type, period = classify(MARKET_TYPES, smt)
        status = (
            "closed" if m.get("closed") else ("open" if m.get("acceptingOrders") else "inactive")
        )
        markets.append(
            MarketRecord(
                venue=CaptureVenue.POLYMARKET,
                market_id=m.get("conditionId") or str(m["id"]),
                event_id=event.event_id,
                venue_market_type=smt,
                bet_type=bet_type,
                period=period,
                line=dec(m.get("line")),
                title=m.get("question") or "",
                status=status,
                start_time=parse_iso(m.get("gameStartTime")) or start,
                books=tuple(
                    BookRef(str(t), str(o)) for t, o in zip(tokens, outcomes, strict=False)
                ),
                raw=m,
            )
        )
    return event, markets


def parse_book(
    raw: dict[str, Any], market_id: str, observed_at: datetime, max_levels: int
) -> BookSnapshot:
    bids = [
        (d, s)
        for lv in raw.get("bids") or []
        if (d := dec(lv["price"])) is not None and (s := dec(lv["size"])) is not None
    ]
    asks = [
        (d, s)
        for lv in raw.get("asks") or []
        if (d := dec(lv["price"])) is not None and (s := dec(lv["size"])) is not None
    ]
    ts = raw.get("timestamp")
    return BookSnapshot(
        venue=CaptureVenue.POLYMARKET,
        market_id=market_id,
        book_key=str(raw["asset_id"]),
        observed_at=observed_at,
        bids=aggregate_levels(bids, descending=True, max_levels=max_levels),
        asks=aggregate_levels(asks, descending=False, max_levels=max_levels),
        venue_ts=from_epoch(int(ts), millis=True) if ts else None,
        extra={"hash": raw.get("hash")} if raw.get("hash") else None,
    )


def parse_trade(
    key: str,
    row: dict[str, Any],
    observed_at: datetime,
    prev_poll_at: datetime | None,
    taker: bool | None,
    source: str = "api",
) -> TradeRecord | None:
    price, size = dec(row.get("price")), dec(row.get("size"))
    if price is None or size is None or not row.get("timestamp"):
        return None
    return TradeRecord(
        venue=CaptureVenue.POLYMARKET,
        trade_key=key,
        market_id=row.get("condition_id", ""),
        book_key=str(row.get("token_id", "")),
        ts=from_epoch(int(row["timestamp"])),
        price=price,
        size=size,
        side=row.get("side"),
        wallet=(row.get("proxy_wallet") or "").lower() or None,
        tx_hash=row.get("transaction_hash"),
        raw=row,
        seen_in_taker_feed=taker,
        observed_at=observed_at,
        prev_poll_at=prev_poll_at,
        source=source,
    )


class PolymarketAdapter(VenueAdapter):
    venue = CaptureVenue.POLYMARKET
    volatile_keys = frozenset(
        {
            "volume", "volume24hr", "volume1wk", "volume1mo", "volume1yr", "volumeNum",
            "volumeClob", "volume24hrClob", "volume1wkClob", "volume1moClob", "volume1yrClob",
            "liquidity", "liquidityNum", "liquidityClob", "openInterest", "competitive",
            "bestBid", "bestAsk", "spread", "lastTradePrice", "outcomePrices",
            "oneHourPriceChange", "oneDayPriceChange", "oneWeekPriceChange",
            "oneMonthPriceChange", "updatedAt", "score", "elapsed", "period", "commentCount",
        }
    )  # fmt: skip

    def __init__(
        self,
        http: VenueHttp,
        *,
        data_http: VenueHttp,
        clob_http: VenueHttp,
        max_levels: int = 50,
        trade_overlap_seconds: int = 120,
    ) -> None:
        super().__init__(http, max_levels=max_levels)
        self.data_http = data_http
        self.clob_http = clob_http
        self.trade_overlap = timedelta(seconds=trade_overlap_seconds)
        # event id -> start time of the last poll that covered it (latency bounds).
        self._last_poll: dict[str, datetime] = {}

    def request_count(self) -> int:
        return self.http.requests + self.data_http.requests + self.clob_http.requests

    async def aclose(self) -> None:
        for h in (self.http, self.data_http, self.clob_http):
            await h.aclose()

    async def fetch_catalog(self, window_start: datetime, window_end: datetime) -> Catalog:
        catalog = Catalog()
        offset = 0
        while True:
            resp = await self.http.get(
                "/events",
                params={
                    "series_id": NFL_SERIES_ID,
                    "closed": "false",
                    "limit": 100,
                    "offset": offset,
                },
            )
            page: list[dict[str, Any]] = resp.data or []
            for raw in page:
                event, markets = parse_event(raw)
                if in_window(event.start_time, window_start, window_end):
                    catalog.events.append(event)
                    catalog.markets.extend(markets)
            if len(page) < 100:
                break
            offset += 100
        return catalog

    async def fetch_books(self, markets: Sequence[MarketRecord]) -> list[BookSnapshot]:
        token_market = {b.book_key: m.market_id for m in markets for b in m.books}
        out: list[BookSnapshot] = []
        for batch in chunks(list(token_market), BOOKS_PER_REQUEST):
            resp = await self.clob_http.post("/books", json=[{"token_id": t} for t in batch])
            observed = datetime.now(UTC)
            for raw in resp.data or []:
                market_id = token_market.get(str(raw.get("asset_id")))
                if market_id:
                    snap = parse_book(raw, market_id, observed, self.max_levels)
                    out.append(replace(snap, request_ms=resp.elapsed_ms))
        return out

    async def fetch_status(self) -> dict[str, Any]:
        resp = await self.data_http.get("/v2/status")
        data: dict[str, Any] = (resp.data or {}).get("data") or {}
        return data

    async def fetch_trades(
        self, markets: Sequence[MarketRecord], checkpoints: dict[str, str]
    ) -> TradeBatch:
        """Poll ``/v2/trades`` by event, newest first, back to the last poll.

        Two passes per event chunk: ``taker_only=false`` (every fill, maker rows
        included) and ``taker_only=true`` (marks which rows are taker fills).
        """
        event_ids = sorted({m.event_id for m in markets})
        event_of = {m.market_id: m.event_id for m in markets}
        batch = TradeBatch(trades=[])
        for group in chunks(event_ids, EVENTS_PER_TRADE_QUERY):
            started = datetime.now(UTC)
            known = [self._last_poll[e] for e in group if e in self._last_poll]
            # Look back to the oldest previous poll in the group, plus overlap
            # for late-indexed fills. New events only look back the overlap.
            floor = (min(known) if known else started) - self.trade_overlap
            prev_by_event = {e: self._last_poll.get(e) for e in group}
            by_key: dict[str, TradeRecord] = {}
            for taker_only in (False, True):
                rows = await self._walk(group, taker_only, floor)
                observed = datetime.now(UTC)
                for key, row in rows:
                    event_prev = prev_by_event.get(event_of.get(row.get("condition_id", ""), ""))
                    if taker_only:
                        if key in by_key:
                            by_key[key] = replace(by_key[key], seen_in_taker_feed=True)
                        continue
                    trade = parse_trade(key, row, observed, event_prev, False)
                    if trade is not None:
                        by_key[key] = trade
            batch.trades.extend(by_key.values())
            for e in group:
                self._last_poll[e] = started
        return batch

    async def _walk(
        self, event_ids: Sequence[str], taker_only: bool, floor: datetime
    ) -> list[tuple[str, dict[str, Any]]]:
        params: dict[str, Any] = {
            "event_id": ",".join(event_ids),
            "limit": TRADE_PAGE,
            "taker_only": "true" if taker_only else "false",
        }
        rows: list[dict[str, Any]] = []
        floor_ts = floor.timestamp()
        while True:
            resp = await self.data_http.get("/v2/trades", params=params)
            body = resp.data or {}
            page: list[dict[str, Any]] = body.get("data") or []
            rows.extend(page)
            cursor = (body.get("pagination") or {}).get("next_cursor")
            if not cursor or not page or page[-1].get("timestamp", 0) < floor_ts:
                break
            params["cursor"] = cursor  # filters must be re-sent on every page
        return keyed_rows([r for r in rows if r.get("timestamp", 0) >= floor_ts])

    async def backfill_event(self, event_id: str) -> list[TradeRecord]:
        """Every fill the Data API serves for one event (three-year window)."""
        params: dict[str, Any] = {"event_id": event_id, "limit": TRADE_PAGE, "taker_only": "false"}
        rows: list[dict[str, Any]] = []
        while True:
            resp = await self.data_http.get("/v2/trades", params=params)
            body = resp.data or {}
            rows.extend(body.get("data") or [])
            cursor = (body.get("pagination") or {}).get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor
        observed = datetime.now(UTC)
        trades = [parse_trade(k, r, observed, None, None) for k, r in keyed_rows(rows)]
        return [t for t in trades if t is not None]
