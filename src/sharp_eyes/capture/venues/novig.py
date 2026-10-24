"""Novig: unsigned public catalog routes (``/v3/public/catalog/*``).

Every Novig order is a buy of one outcome, so a market's book is a list of
resting buys per outcome. A buy of the other outcome at p is an offer of this
outcome at 1 - p. One Novig contract pays 1 cent; sizes are divided by 100 to
count $1-payout contracts. The REST book has ``seq`` but no timestamp.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sharp_eyes.capture.http import VenueHttp, VenueHttpError
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
    collect,
    dec,
    from_epoch,
    gather_limited,
    in_window,
)

log = logging.getLogger(__name__)

API = "https://api.novig.com"
CONTRACT_VALUE = Decimal("0.01")  # USD paid by one winning Novig contract
PAGE = 5000

_B, _P = BetType, Period
MARKET_TYPES: dict[str, tuple[BetType, Period]] = {
    "MONEY": (_B.MONEYLINE, _P.FULL_GAME),
    "SPREAD": (_B.SPREAD, _P.FULL_GAME),
    "TOTAL": (_B.TOTAL, _P.FULL_GAME),
    "TEAM_TOTAL": (_B.TEAM_TOTAL, _P.FULL_GAME),
    "MONEY_1H": (_B.MONEYLINE, _P.FIRST_HALF),
    "SPREAD_1H": (_B.SPREAD, _P.FIRST_HALF),
    "TOTAL_1H": (_B.TOTAL, _P.FIRST_HALF),
}
DEFAULT_MARKET_TYPES = ("MONEY", "SPREAD", "TOTAL", "TEAM_TOTAL", "SPREAD_1H", "TOTAL_1H")


def classify_market(market_type: str) -> tuple[BetType, Period]:
    if market_type in MARKET_TYPES:
        return MARKET_TYPES[market_type]
    return BetType.PROP, Period.FULL_GAME  # Every other Novig NFL type is a player prop


def contracts(qty: Any) -> Decimal | None:
    q = dec(qty)
    return None if q is None else q * CONTRACT_VALUE


def parse_event(raw: dict[str, Any]) -> EventRecord:
    return EventRecord(
        venue=CaptureVenue.NOVIG,
        event_id=raw["eventId"],
        league=raw.get("league") or "NFL",
        title=raw.get("description") or raw["eventId"],
        start_time=from_epoch(raw["startsTs"], millis=True) if raw.get("startsTs") else None,
        status=raw.get("status") or "unknown",
        raw=raw,
    )


def parse_market(raw: dict[str, Any]) -> MarketRecord:
    bet_type, period = classify_market(raw.get("marketType") or "")
    return MarketRecord(
        venue=CaptureVenue.NOVIG,
        market_id=raw["marketId"],
        event_id=raw["eventId"],
        venue_market_type=raw.get("marketType") or "",
        bet_type=bet_type,
        period=period,
        line=dec(raw.get("strike")),
        title=raw.get("description") or "",
        status=raw.get("status") or "unknown",
        start_time=from_epoch(raw["startsTs"], millis=True) if raw.get("startsTs") else None,
        books=tuple(
            BookRef(o["outcomeId"], o.get("name") or "") for o in raw.get("outcomes") or []
        ),
        raw=raw,
    )


def parse_book(
    market: MarketRecord, raw: dict[str, Any], observed_at: datetime, max_levels: int
) -> list[BookSnapshot]:
    orders: dict[str, list[dict[str, Any]]] = raw.get("orders") or {}
    bids: dict[str, tuple[tuple[Decimal, Decimal], ...]] = {}
    for ref in market.books:
        levels = []
        for o in orders.get(ref.book_key) or []:
            p, q = dec(o.get("price")), contracts(o.get("qty"))
            if p is not None and q is not None:
                levels.append((p, q))
        bids[ref.book_key] = aggregate_levels(levels, descending=True, max_levels=max_levels)
    out = []
    for ref in market.books:
        others = [k for k in bids if k != ref.book_key]
        asks = complement(bids[others[0]]) if len(market.books) == 2 else ()
        out.append(
            BookSnapshot(
                venue=CaptureVenue.NOVIG,
                market_id=market.market_id,
                book_key=ref.book_key,
                observed_at=observed_at,
                bids=bids[ref.book_key],
                asks=asks,
                seq=raw.get("seq"),
            )
        )
    return out


def parse_trade(market_id: str, raw: dict[str, Any], observed_at: datetime) -> TradeRecord | None:
    price, size = dec(raw.get("price")), contracts(raw.get("qty"))
    if price is None or size is None or not raw.get("tradeId") or not raw.get("ts"):
        return None
    return TradeRecord(
        venue=CaptureVenue.NOVIG,
        trade_key=raw["tradeId"],
        market_id=market_id,
        book_key=raw.get("outcomeId", ""),
        ts=from_epoch(raw["ts"], millis=True),
        price=price,  # Price of the outcome bought by this side of the fill
        size=size,
        raw=raw,
        observed_at=observed_at,
    )


@dataclass(frozen=True)
class _TradeCheckpoint:
    volume: str
    newest_trade_id: str
    newest_ts_ms: int

    @classmethod
    def parse(cls, value: str | None) -> _TradeCheckpoint | None:
        if not value:
            return None
        volume, trade_id, ts = value.split("|")
        return cls(volume, trade_id, int(ts))

    def dump(self) -> str:
        return f"{self.volume}|{self.newest_trade_id}|{self.newest_ts_ms}"


class NovigAdapter(VenueAdapter):
    venue = CaptureVenue.NOVIG
    volatile_keys = frozenset({"bid", "volume", "openInterest"})

    def __init__(
        self,
        http: VenueHttp,
        *,
        market_types: Sequence[str] = DEFAULT_MARKET_TYPES,
        max_levels: int = 20,
        concurrency: int = 4,
        max_markets_per_poll: int = 100,
    ) -> None:
        super().__init__(http, max_levels=max_levels, concurrency=concurrency)
        self.max_markets_per_poll = max_markets_per_poll
        self.market_types = tuple(market_types)
        self._etags: dict[str, str] = {}

    async def _pages(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        params = dict(params)
        while True:
            resp = await self.http.get(path, params=params)
            body = resp.data or {}
            items.extend(body.get("items") or [])
            if not body.get("next"):
                return items
            params["after"] = body["next"]

    async def fetch_catalog(self, window_start: datetime, window_end: datetime) -> Catalog:
        events = [
            parse_event(e)
            for e in await self._pages(
                "/v3/public/catalog/events", {"league": "NFL", "limit": PAGE}
            )
        ]
        events = [e for e in events if in_window(e.start_time, window_start, window_end)]
        wanted = {e.event_id for e in events}
        raw_markets = await self._pages(
            "/v3/public/catalog/markets",
            {"league": "NFL", "marketType": ",".join(self.market_types), "limit": PAGE},
        )
        markets = [parse_market(m) for m in raw_markets if m.get("eventId") in wanted]
        return Catalog(events=events, markets=markets)

    async def fetch_books(self, markets: Sequence[MarketRecord]) -> list[BookSnapshot]:
        async def one(m: MarketRecord) -> list[BookSnapshot]:
            headers = (
                {"If-None-Match": self._etags[m.market_id]} if m.market_id in self._etags else None
            )
            try:
                resp = await self.http.get(
                    f"/v3/public/catalog/markets/{m.market_id}/book",
                    params={"depth": 20},
                    headers=headers,
                    ok_statuses=frozenset({200, 304}),
                )
            except VenueHttpError as exc:
                if exc.status == 404:  # Market left the open set
                    return []
                raise
            if resp.status == 304:
                return []  # Unchanged since our last stored snapshot
            if etag := resp.headers.get("etag"):
                self._etags[m.market_id] = etag
            snaps = parse_book(m, resp.data or {}, datetime.now(UTC), self.max_levels)
            return [replace(s, request_ms=resp.elapsed_ms) for s in snaps]

        results = await gather_limited(markets, one, self.concurrency)
        return [s for group in collect(results, log, self.venue) for s in group]

    async def fetch_trades(
        self, markets: Sequence[MarketRecord], checkpoints: dict[str, str]
    ) -> TradeBatch:
        """Fetch trades only for markets whose catalog volume moved."""
        due = []
        for m in markets:
            cp = _TradeCheckpoint.parse(checkpoints.get(f"trades:{m.market_id}"))
            volume = str(m.raw.get("volume", ""))
            if cp is None or cp.volume != volume:
                due.append((m, cp, volume))
        # Bound each poll; markets left over stay due and go first next time.
        due.sort(key=lambda d: d[0].start_time or datetime.max.replace(tzinfo=UTC))
        due = due[: self.max_markets_per_poll]

        async def one(
            item: tuple[MarketRecord, _TradeCheckpoint | None, str],
        ) -> tuple[str, str, list[TradeRecord]]:
            m, cp, volume = item
            trades = await self._market_trades(m.market_id, cp)
            newest = max(trades, key=lambda t: t.ts, default=None)
            if newest is not None:
                new_cp = _TradeCheckpoint(
                    volume, newest.trade_key, int(newest.ts.timestamp() * 1000)
                )
            elif cp is not None:
                new_cp = replace(cp, volume=volume)
            else:
                new_cp = _TradeCheckpoint(volume, "", 0)
            return f"trades:{m.market_id}", new_cp.dump(), trades

        batch = TradeBatch(trades=[])
        for key, value, trades in collect(
            await gather_limited(due, one, self.concurrency), log, self.venue
        ):
            batch.trades.extend(trades)
            batch.checkpoints[key] = value
        return batch

    async def _market_trades(
        self, market_id: str, cp: _TradeCheckpoint | None
    ) -> list[TradeRecord]:
        params: dict[str, Any] = {"limit": 500}
        floor_ms = (
            cp.newest_ts_ms - int(timedelta(minutes=2).total_seconds() * 1000) if cp else None
        )
        out: list[TradeRecord] = []
        while True:
            resp = await self.http.get(
                f"/v3/public/catalog/markets/{market_id}/trades", params=params
            )
            observed = datetime.now(UTC)
            body = resp.data or {}
            page = body.get("items") or []
            stop = False
            for raw in page:  # Newest first
                if cp and (
                    raw.get("tradeId") == cp.newest_trade_id or raw.get("ts", 0) < (floor_ms or 0)
                ):
                    stop = True
                    break
                trade = parse_trade(market_id, raw, observed)
                if trade is not None:
                    out.append(trade)
            # Without a checkpoint take only the newest page: older fills are in
            # Novig's daily trade CSVs, and paging every market's full history
            # on startup would exhaust the per-IP throttle.
            if stop or cp is None or not body.get("next") or not page:
                return out
            params["after"] = body["next"]
