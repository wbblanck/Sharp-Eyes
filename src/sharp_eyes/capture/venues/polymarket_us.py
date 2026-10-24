"""Polymarket US public gateway: catalog and books.

The public gateway has no trade tape. The full tape is only on the
authenticated markets websocket, which needs a Polymarket US API key. Until we
have one, each book snapshot keeps the market stats the gateway returns (last
trade price, quantity and time, shares traded, open interest), which bound the
traded volume between snapshots.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sharp_eyes.capture.http import VenueHttpError
from sharp_eyes.capture.records import (
    BetType,
    BookRef,
    BookSnapshot,
    CaptureVenue,
    EventRecord,
    MarketRecord,
    Period,
    aggregate_levels,
)
from sharp_eyes.capture.venues.base import (
    Catalog,
    TradeBatch,
    VenueAdapter,
    classify,
    collect,
    dec,
    gather_limited,
    in_window,
    parse_iso,
)

log = logging.getLogger(__name__)

GATEWAY = "https://gateway.polymarket.us"

_B, _P = BetType, Period
_QUARTERS = {"first": "1Q", "second": "2Q", "third": "3Q", "fourth": "4Q"}
MARKET_TYPES: dict[str, tuple[BetType, Period]] = {
    "football_team_full_game_winner": (_B.MONEYLINE, _P.FULL_GAME),
    "football_team_full_game_spread": (_B.SPREAD, _P.FULL_GAME),
    "football_team_full_game_total": (_B.TOTAL, _P.FULL_GAME),
    "football_team_points_full_game_total": (_B.TEAM_TOTAL, _P.FULL_GAME),
    "football_team_first_half_winner": (_B.MONEYLINE, _P.FIRST_HALF),
    "football_team_first_half_spread": (_B.SPREAD, _P.FIRST_HALF),
    "football_game_first_half_total": (_B.TOTAL, _P.FIRST_HALF),
    "football_team_first_half_total": (_B.TEAM_TOTAL, _P.FIRST_HALF),
    "football_team_second_half_winner": (_B.MONEYLINE, _P.SECOND_HALF),
    "football_team_second_half_spread": (_B.SPREAD, _P.SECOND_HALF),
    "football_game_second_half_total": (_B.TOTAL, _P.SECOND_HALF),
    "football_team_second_half_total": (_B.TEAM_TOTAL, _P.SECOND_HALF),
    **{
        f"football_team_{q}_quarter_winner": (_B.MONEYLINE, Period(p)) for q, p in _QUARTERS.items()
    },
    **{f"football_team_{q}_quarter_spread": (_B.SPREAD, Period(p)) for q, p in _QUARTERS.items()},
    **{f"football_game_{q}_quarter_total": (_B.TOTAL, Period(p)) for q, p in _QUARTERS.items()},
}


def classify_market(smt: str) -> tuple[BetType, Period]:
    if smt.startswith("football_player_"):
        return BetType.PROP, Period.FULL_GAME
    return classify(MARKET_TYPES, smt)


def parse_event(raw: dict[str, Any]) -> tuple[EventRecord, list[MarketRecord]]:
    start = parse_iso(raw.get("startTime")) or parse_iso(raw.get("startDate"))
    status = "closed" if raw.get("closed") else ("ended" if raw.get("ended") else
              ("live" if raw.get("live") else "open"))  # fmt: skip
    event = EventRecord(
        venue=CaptureVenue.POLYMARKET_US,
        event_id=str(raw["id"]),
        league="NFL",
        title=raw.get("title") or raw.get("slug") or "",
        start_time=start,
        status=status,
        raw={k: v for k, v in raw.items() if k not in ("markets", "marketGroups")},
    )
    markets = []
    for m in raw.get("markets") or []:
        slug = m.get("slug")
        if not slug:
            continue
        smt = m.get("sportsMarketType") or ""
        bet_type, period = classify_market(smt)
        long_side = next((s for s in m.get("marketSides") or [] if s.get("long")), None)
        outcome = (long_side or {}).get("description") or "long"
        markets.append(
            MarketRecord(
                venue=CaptureVenue.POLYMARKET_US,
                market_id=slug,
                event_id=event.event_id,
                venue_market_type=smt,
                bet_type=bet_type,
                period=period,
                line=dec(m.get("line")),
                title=m.get("question") or m.get("title") or "",
                status="closed" if m.get("closed") else ("open" if m.get("active") else "inactive"),
                start_time=parse_iso(m.get("gameStartTime")) or start,
                # One book per market, quoted on the long side; the short side
                # is its complement.
                books=(BookRef(slug, str(outcome)),),
                raw=m,
            )
        )
    return event, markets


def parse_book(raw: dict[str, Any], observed_at: datetime, max_levels: int) -> BookSnapshot:
    md = raw.get("marketData") or {}

    def levels(key: str) -> list[tuple[Any, Any]]:
        out = []
        for lv in md.get(key) or []:
            p, q = dec((lv.get("px") or {}).get("value")), dec(lv.get("qty"))
            if p is not None and q is not None:
                out.append((p, q))
        return out

    extra: dict[str, Any] = {"state": md.get("state")}
    if md.get("stats"):
        extra["stats"] = md["stats"]
    return BookSnapshot(
        venue=CaptureVenue.POLYMARKET_US,
        market_id=md.get("marketSlug", ""),
        book_key=md.get("marketSlug", ""),
        observed_at=observed_at,
        bids=aggregate_levels(levels("bids"), descending=True, max_levels=max_levels),
        asks=aggregate_levels(levels("offers"), descending=False, max_levels=max_levels),
        venue_ts=parse_iso(md.get("transactTime")),
        extra=extra,
    )


class PolymarketUSAdapter(VenueAdapter):
    venue = CaptureVenue.POLYMARKET_US
    volatile_keys = frozenset(
        {
            "volume", "volume24hr", "volume1wk", "volume1mo", "volume1yr", "liquidity",
            "openInterest", "updatedAt", "price", "quote", "bestBidQuote", "bestAskQuote",
            "outcomePrices", "score", "elapsed", "period", "record", "chatChannel",
            "eventState", "metadata", "ep3SyncedAt", "chatMemberCount",
        }
    )  # fmt: skip

    async def fetch_catalog(self, window_start: datetime, window_end: datetime) -> Catalog:
        listed: list[dict[str, Any]] = []
        offset = 0
        while True:
            resp = await self.http.get(
                "/v2/leagues/nfl/events", params={"limit": 100, "offset": offset}
            )
            page = (resp.data or {}).get("events") or []
            listed.extend(page)
            if len(page) < 100:
                break
            offset += 100
        catalog = Catalog()
        for summary in listed:
            if not in_window(parse_iso(summary.get("startTime")), window_start, window_end):
                continue
            # The league listing carries only the moneyline; the event route has
            # every market.
            resp = await self.http.get(f"/v1/events/{summary['id']}")
            event, markets = parse_event((resp.data or {}).get("event") or summary)
            catalog.events.append(event)
            catalog.markets.extend(markets)
        return catalog

    async def fetch_books(self, markets: Sequence[MarketRecord]) -> list[BookSnapshot]:
        async def one(m: MarketRecord) -> BookSnapshot | None:
            try:
                resp = await self.http.get(f"/v1/markets/{m.market_id}/book")
            except VenueHttpError as exc:
                if exc.status == 404:
                    return None
                raise
            snap = parse_book(resp.data or {}, datetime.now(UTC), self.max_levels)
            return replace(snap, market_id=m.market_id, request_ms=resp.elapsed_ms)

        results = await gather_limited(markets, one, self.concurrency)
        return collect(results, log, self.venue)

    async def fetch_trades(
        self, markets: Sequence[MarketRecord], checkpoints: dict[str, str]
    ) -> TradeBatch:
        return TradeBatch(trades=[])  # No public tape; see module docstring.
