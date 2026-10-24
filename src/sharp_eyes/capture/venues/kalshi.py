"""Kalshi: series-based NFL catalog, batched order books, the public trade tape.

Kalshi books carry bids only: ``yes`` bids and ``no`` bids, ascending. A yes ask
at p is a no bid at 1 - p. Kalshi sends 429 without ``Retry-After``.
"""

from __future__ import annotations

import logging
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
    complement,
)
from sharp_eyes.capture.venues.base import (
    Catalog,
    TradeBatch,
    VenueAdapter,
    chunks,
    dec,
    in_window,
    parse_iso,
)

log = logging.getLogger(__name__)

API = "https://external-api.kalshi.com/trade-api/v2"
BOOKS_PER_REQUEST = 100  # /markets/orderbooks rejects more than 100 tickers
TRADE_PAGE = 1000
# Kalshi game events have no kickoff field. Game markets expect to expire about
# three hours after kickoff, so start = expected expiration - 3 h (an estimate,
# flagged on the event). It is only used to choose polling cadence.
GAME_LENGTH = timedelta(hours=3)

_B, _P = BetType, Period
SERIES: dict[str, tuple[BetType, Period]] = {
    "KXNFLGAME": (_B.MONEYLINE, _P.FULL_GAME),
    "KXNFLSPREAD": (_B.SPREAD, _P.FULL_GAME),
    "KXNFLTOTAL": (_B.TOTAL, _P.FULL_GAME),
    "KXNFLTEAMTOTAL": (_B.TEAM_TOTAL, _P.FULL_GAME),
    "KXNFL1H": (_B.MONEYLINE, _P.FIRST_HALF),
    "KXNFL1HSPREAD": (_B.SPREAD, _P.FIRST_HALF),
    "KXNFL1HTOTAL": (_B.TOTAL, _P.FIRST_HALF),
    "KXNFL1Q": (_B.MONEYLINE, _P.Q1),
    "KXNFL1QSPREAD": (_B.SPREAD, _P.Q1),
    "KXNFL1QTOTAL": (_B.TOTAL, _P.Q1),
}
DEFAULT_SERIES = ("KXNFLGAME", "KXNFLSPREAD", "KXNFLTOTAL", "KXNFLTEAMTOTAL")


def series_of(ticker: str) -> str:
    return ticker.split("-", 1)[0]


def parse_event(raw: dict[str, Any]) -> tuple[EventRecord, list[MarketRecord]]:
    series = raw.get("series_ticker") or series_of(raw["event_ticker"])
    bet_type, period = SERIES.get(series, (BetType.OTHER, Period.OTHER))
    nested = raw.get("markets") or []
    expiries = [t for m in nested if (t := parse_iso(m.get("expected_expiration_time")))]
    start = min(expiries) - GAME_LENGTH if expiries else None
    statuses = {m.get("status") for m in nested}
    event = EventRecord(
        venue=CaptureVenue.KALSHI,
        event_id=raw["event_ticker"],
        league="NFL",
        title=raw.get("title") or raw["event_ticker"],
        start_time=start,
        status="open" if "active" in statuses else next((x for x in statuses if x), "unknown"),
        raw={**{k: v for k, v in raw.items() if k != "markets"}, "_start_time_estimated": True},
    )
    markets = [
        MarketRecord(
            venue=CaptureVenue.KALSHI,
            market_id=m["ticker"],
            event_id=event.event_id,
            venue_market_type=series,
            bet_type=bet_type,
            period=period,
            line=dec(m.get("floor_strike")),
            title=m.get("title") or m["ticker"],
            status=m.get("status") or "unknown",
            start_time=start,
            books=(BookRef(m["ticker"], m.get("yes_sub_title") or "yes"),),
            raw=m,
        )
        for m in nested
        if m.get("ticker") and not m.get("mve_collection_ticker")
    ]
    return event, markets


def _levels(rows: Any) -> list[tuple[Any, Any]]:
    out = []
    for row in rows or []:
        p, q = dec(row[0]), dec(row[1])
        if p is not None and q is not None:
            out.append((p, q))
    return out


def parse_book(
    ticker: str, raw: dict[str, Any], observed_at: datetime, max_levels: int
) -> BookSnapshot:
    book = raw.get("orderbook_fp") or raw.get("orderbook") or {}
    yes = aggregate_levels(_levels(book.get("yes_dollars")), descending=True, max_levels=max_levels)
    no = aggregate_levels(_levels(book.get("no_dollars")), descending=True, max_levels=max_levels)
    return BookSnapshot(
        venue=CaptureVenue.KALSHI,
        market_id=ticker,
        book_key=ticker,
        observed_at=observed_at,
        bids=yes,
        asks=complement(no),
    )


def parse_trade(raw: dict[str, Any], observed_at: datetime) -> TradeRecord | None:
    ts = parse_iso(raw.get("created_time"))
    price, size = dec(raw.get("yes_price_dollars")), dec(raw.get("count_fp"))
    if ts is None or price is None or size is None or not raw.get("trade_id"):
        return None
    return TradeRecord(
        venue=CaptureVenue.KALSHI,
        trade_key=raw["trade_id"],
        market_id=raw["ticker"],
        book_key=raw["ticker"],
        ts=ts,
        price=price,  # Yes price; the no price is 1 - price
        size=size,
        taker_side=raw.get("taker_side"),
        raw=raw,
        observed_at=observed_at,
    )


class KalshiAdapter(VenueAdapter):
    venue = CaptureVenue.KALSHI
    volatile_keys = frozenset(
        {
            "last_price_dollars", "previous_price_dollars", "previous_yes_ask_dollars",
            "previous_yes_bid_dollars", "yes_ask_dollars", "yes_bid_dollars", "no_ask_dollars",
            "no_bid_dollars", "yes_ask_size_fp", "yes_bid_size_fp", "volume_fp",
            "volume_24h_fp", "open_interest_fp", "liquidity_dollars", "updated_time",
            "last_updated_ts",
        }
    )  # fmt: skip

    def __init__(
        self,
        http: VenueHttp,
        *,
        series: Sequence[str] = DEFAULT_SERIES,
        max_levels: int = 50,
        trade_overlap_seconds: int = 30,
        initial_trade_lookback_seconds: int = 600,
    ) -> None:
        super().__init__(http, max_levels=max_levels)
        self.series = tuple(series)
        self.trade_overlap = trade_overlap_seconds
        self.initial_lookback = initial_trade_lookback_seconds

    async def fetch_catalog(self, window_start: datetime, window_end: datetime) -> Catalog:
        catalog = Catalog()
        for series in self.series:
            cursor = None
            while True:
                params: dict[str, Any] = {
                    "series_ticker": series,
                    "status": "open",
                    "with_nested_markets": "true",
                    "limit": 200,
                }
                if cursor:
                    params["cursor"] = cursor
                resp = await self.http.get("/events", params=params)
                body = resp.data or {}
                for raw in body.get("events") or []:
                    event, markets = parse_event(raw)
                    if in_window(event.start_time, window_start, window_end):
                        catalog.events.append(event)
                        catalog.markets.extend(markets)
                cursor = body.get("cursor")
                if not cursor:
                    break
        return catalog

    async def fetch_books(self, markets: Sequence[MarketRecord]) -> list[BookSnapshot]:
        tickers = [m.market_id for m in markets]
        out: list[BookSnapshot] = []
        for batch in chunks(tickers, BOOKS_PER_REQUEST):
            resp = await self.http.get(
                "/markets/orderbooks", params=[("tickers", t) for t in batch]
            )
            observed = datetime.now(UTC)
            for raw in (resp.data or {}).get("orderbooks") or []:
                if raw.get("ticker") in batch:
                    snap = parse_book(raw["ticker"], raw, observed, self.max_levels)
                    out.append(replace(snap, request_ms=resp.elapsed_ms))
        return out

    async def fetch_trades(
        self, markets: Sequence[MarketRecord], checkpoints: dict[str, str]
    ) -> TradeBatch:
        """Walk the global tape since the checkpoint and keep tracked series.

        Per-ticker polling would cost one request per market; the global tape
        costs about one request per thousand trades venue-wide.
        """
        now = int(datetime.now(UTC).timestamp())
        last = checkpoints.get("trades:global")
        min_ts = int(last) - self.trade_overlap if last else now - self.initial_lookback
        prefixes = tuple(f"{s}-" for s in self.series)
        params: dict[str, Any] = {"limit": TRADE_PAGE, "min_ts": min_ts}
        trades: list[TradeRecord] = []
        newest = int(last) if last else min_ts
        while True:
            resp = await self.http.get("/markets/trades", params=params)
            observed = datetime.now(UTC)
            body = resp.data or {}
            page = body.get("trades") or []
            for raw in page:
                if not str(raw.get("ticker", "")).startswith(prefixes):
                    continue
                trade = parse_trade(raw, observed)
                if trade is not None:
                    trades.append(trade)
                    newest = max(newest, int(trade.ts.timestamp()))
            cursor = body.get("cursor")
            if not cursor or not page:
                break
            params["cursor"] = cursor
        # Never move the checkpoint past this poll's start: a trade stamped just
        # before ``now`` could still be indexing.
        return TradeBatch(
            trades=trades, checkpoints={"trades:global": str(min(now, max(newest, min_ts)))}
        )
