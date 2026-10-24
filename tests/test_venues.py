"""Adapter parsing and polling logic against canned responses shaped like the live APIs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from typing import Any

import httpx

from sharp_eyes.capture.records import BetType, Period
from sharp_eyes.capture.venues import kalshi, novig, polymarket, polymarket_us
from tests.conftest import json_response, mock_http

NOW = datetime.now(UTC)


# -- Polymarket ---------------------------------------------------------------


def pm_event() -> dict[str, Any]:
    return {
        "id": "1022434",
        "slug": "nfl-pit-no-2026-10-25",
        "title": "Steelers vs. Saints",
        "startTime": (NOW + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "closed": False,
        "markets": [
            {
                "id": "1",
                "conditionId": "0xml",
                "question": "Steelers vs. Saints",
                "sportsMarketType": "moneyline",
                "line": None,
                "outcomes": '["Steelers", "Saints"]',
                "clobTokenIds": '["111", "222"]',
                "acceptingOrders": True,
                "closed": False,
                "gameStartTime": "2026-10-25 13:30:00+00",
            },
            {
                "id": "2",
                "conditionId": "0xq1",
                "question": "1Q spread",
                "sportsMarketType": "q1_spreads",
                "line": -1.5,
                "outcomes": '["Steelers", "Saints"]',
                "clobTokenIds": '["333", "444"]',
                "acceptingOrders": True,
            },
        ],
    }


def pm_trade(ts: int, wallet: str, size: float = 5.0, tx: str = "0xtx") -> dict[str, Any]:
    return {
        "proxy_wallet": wallet,
        "side": "BUY",
        "token_id": "111",
        "condition_id": "0xml",
        "size": size,
        "price": 0.6,
        "timestamp": ts,
        "transaction_hash": tx,
        "event_slug": "nfl-pit-no-2026-10-25",
    }


def test_polymarket_event_parsing_and_classification() -> None:
    event, markets = polymarket.parse_event(pm_event())
    assert event.event_id == "1022434" and event.status == "open"
    ml, q1 = markets
    assert (ml.bet_type, ml.period, ml.is_core) == (BetType.MONEYLINE, Period.FULL_GAME, True)
    assert (q1.bet_type, q1.period, q1.line) == (BetType.SPREAD, Period.Q1, D("-1.5"))
    assert [b.book_key for b in ml.books] == ["111", "222"]
    assert ml.start_time == datetime(2026, 10, 25, 13, 30, tzinfo=UTC)


def test_polymarket_book_is_best_first() -> None:
    raw = {
        "asset_id": "111",
        "timestamp": "1792816153528",
        "hash": "abc",
        "bids": [{"price": "0.01", "size": "10"}, {"price": "0.59", "size": "5"}],
        "asks": [{"price": "0.99", "size": "1"}, {"price": "0.61", "size": "7"}],
    }
    snap = polymarket.parse_book(raw, "0xml", NOW, 50)
    assert snap.best_bid == D("0.59") and snap.best_ask == D("0.61")
    assert snap.venue_ts == datetime.fromtimestamp(1792816153.528, UTC)


def test_polymarket_trade_keys_split_identical_fills() -> None:
    rows = [pm_trade(100, "0xa"), pm_trade(100, "0xa"), pm_trade(100, "0xb")]
    keys = [k for k, _ in polymarket.keyed_rows(rows)]
    assert len(set(keys)) == 3
    assert keys[0].endswith("|0") and keys[1].endswith("|1") and keys[2].endswith("|0")


async def test_polymarket_trade_polls_mark_takers_and_bound_latency() -> None:
    now_ts = int(NOW.timestamp())
    feed: list[dict[str, Any]] = [pm_trade(now_ts - 5, "0xmaker"), pm_trade(now_ts - 5, "0xtaker")]
    seen_params: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen_params.append(params)
        rows = (
            feed
            if params["taker_only"] == "false"
            else [r for r in feed if r["proxy_wallet"] == "0xtaker"]
        )
        return json_response({"data": rows, "pagination": {"has_more": False, "next_cursor": None}})

    http = mock_http(handler)
    adapter = polymarket.PolymarketAdapter(http, data_http=http, clob_http=http)
    _, markets = polymarket.parse_event(pm_event())

    first = await adapter.fetch_trades(markets, {})
    assert {t.wallet: t.seen_in_taker_feed for t in first.trades} == {
        "0xmaker": False,
        "0xtaker": True,
    }
    assert all(t.prev_poll_at is None for t in first.trades)  # First poll: no latency sample
    assert seen_params[0]["event_id"] == "1022434"

    feed.insert(0, pm_trade(now_ts, "0xnew", tx="0xtx2"))
    second = await adapter.fetch_trades(markets, {})
    new = next(t for t in second.trades if t.wallet == "0xnew")
    assert new.prev_poll_at is not None and new.observed_at is not None
    assert new.prev_poll_at <= new.observed_at


async def test_polymarket_backfill_follows_cursor() -> None:
    pages = {
        None: {"data": [pm_trade(10, "0xa")], "pagination": {"next_cursor": "c1"}},
        "c1": {"data": [pm_trade(9, "0xb")], "pagination": {"next_cursor": None}},
    }
    http = mock_http(lambda r: json_response(pages[r.url.params.get("cursor")]))
    adapter = polymarket.PolymarketAdapter(http, data_http=http, clob_http=http)
    trades = await adapter.backfill_event("1022434")
    assert [t.wallet for t in trades] == ["0xa", "0xb"]
    assert all(t.prev_poll_at is None for t in trades)


# -- Polymarket US ------------------------------------------------------------


def test_polymarket_us_event_and_book() -> None:
    raw = {
        "id": "154442",
        "title": "PIT Steelers vs. NO Saints",
        "startTime": "2026-10-25T13:30:00Z",
        "markets": [
            {
                "slug": "aec-nfl-pit-no-2026-10-25",
                "sportsMarketType": "football_team_full_game_winner",
                "active": True,
                "marketSides": [
                    {"description": "Steelers", "long": True},
                    {"description": "Saints"},
                ],
            },
            {
                "slug": "x-total",
                "sportsMarketType": "football_team_full_game_total",
                "line": 44.5,
                "active": True,
            },
            {
                "slug": "x-tt",
                "sportsMarketType": "football_team_points_full_game_total",
                "active": True,
            },
            {"slug": "x-prop", "sportsMarketType": "football_player_rushing_yards", "active": True},
        ],
    }
    _, markets = polymarket_us.parse_event(raw)
    assert [(m.bet_type, m.is_core) for m in markets] == [
        (BetType.MONEYLINE, True),
        (BetType.TOTAL, True),
        (BetType.TEAM_TOTAL, False),
        (BetType.PROP, False),
    ]
    assert markets[0].books[0].outcome == "Steelers"

    book = {
        "marketData": {
            "marketSlug": "aec-nfl-pit-no-2026-10-25",
            "bids": [{"px": {"value": "0.6050", "currency": "USD"}, "qty": "250000.0000"},
                     {"px": {"value": "0.6075", "currency": "USD"}, "qty": "45872.39"}],
            "offers": [{"px": {"value": "0.6100", "currency": "USD"}, "qty": "100"}],
            "state": "MARKET_STATE_OPEN",
            "stats": {"lastTradePx": {"value": "0.61"}, "lastTradeQty": "15.95"},
            "transactTime": "2026-10-24T04:30:01Z",
        }
    }  # fmt: skip
    snap = polymarket_us.parse_book(book, NOW, 50)
    assert snap.best_bid == D("0.6075") and snap.best_ask == D("0.6100")
    assert snap.extra is not None and snap.extra["stats"]["lastTradeQty"] == "15.95"


# -- Kalshi -------------------------------------------------------------------


def test_kalshi_event_book_and_trade_parsing() -> None:
    expiry = (NOW + timedelta(hours=5)).isoformat()
    raw = {
        "event_ticker": "KXNFLSPREAD-26OCT25PITNO",
        "series_ticker": "KXNFLSPREAD",
        "title": "Pittsburgh vs New Orleans: Spread",
        "markets": [
            {"ticker": "KXNFLSPREAD-26OCT25PITNO-PIT3", "floor_strike": 2.5, "status": "active",
             "expected_expiration_time": expiry, "yes_sub_title": "PIT by over 2.5"},
            {"ticker": "KXMVE-X", "mve_collection_ticker": "KXMVE", "status": "active"},
        ],
    }  # fmt: skip
    event, markets = kalshi.parse_event(raw)
    assert event.status == "open" and event.raw["_start_time_estimated"] is True
    assert event.start_time is not None and abs(
        event.start_time - (NOW + timedelta(hours=2))
    ) < timedelta(seconds=1)
    assert (
        len(markets) == 1 and markets[0].bet_type is BetType.SPREAD and markets[0].line == D("2.5")
    )

    book = {"orderbook_fp": {"yes_dollars": [["0.56", "10"], ["0.60", "5"]],
                             "no_dollars": [["0.35", "3"], ["0.39", "8"]]}}  # fmt: skip
    snap = kalshi.parse_book("T", book, NOW, 50)
    assert snap.bids[0] == (D("0.60"), D("5")) and snap.asks[0] == (D("0.61"), D("8"))

    trade = kalshi.parse_trade(
        {"trade_id": "abc", "ticker": "T", "created_time": "2026-10-24T04:31:03.381929Z",
         "yes_price_dollars": "0.6100", "count_fp": "15.95", "taker_side": "yes"},
        NOW,
    )  # fmt: skip
    assert trade is not None and trade.size == D("15.95") and trade.ts.microsecond == 381929


async def test_kalshi_trades_filter_series_and_advance_checkpoint() -> None:
    pages = {
        None: {"trades": [
            {"trade_id": "1", "ticker": "KXNFLGAME-26OCT25PITNO-PIT", "created_time": "2026-10-24T04:30:00Z",
             "yes_price_dollars": "0.61", "count_fp": "1"},
            {"trade_id": "2", "ticker": "KXNBAGAME-26OCT23MEMGSW-MEM", "created_time": "2026-10-24T04:30:01Z",
             "yes_price_dollars": "0.82", "count_fp": "1"},
        ], "cursor": "next"},
        "next": {"trades": [], "cursor": ""},
    }  # fmt: skip
    seen: list[dict[str, str]] = []

    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(dict(r.url.params))
        return json_response(pages[r.url.params.get("cursor")])

    adapter = kalshi.KalshiAdapter(
        mock_http(handler), series=["KXNFLGAME"], trade_overlap_seconds=30
    )
    batch = await adapter.fetch_trades([], {"trades:global": "1792816000"})
    assert [t.trade_key for t in batch.trades] == ["1"]
    assert seen[0]["min_ts"] == str(1792816000 - 30)
    assert int(batch.checkpoints["trades:global"]) >= 1792816000


# -- Novig --------------------------------------------------------------------


def novig_market(volume: int = 100) -> dict[str, Any]:
    return {
        "marketId": "m1",
        "eventId": "e1",
        "description": "BUF",
        "marketType": "MONEY",
        "strike": "0",
        "status": "OPEN",
        "startsTs": int((NOW + timedelta(days=1)).timestamp() * 1000),
        "outcomes": [{"outcomeId": "buf", "name": "BUF"}, {"outcomeId": "bal", "name": "BAL"}],
        "volume": volume,
    }


def test_novig_book_scales_contracts_and_derives_asks() -> None:
    market = novig.parse_market(novig_market())
    assert market.is_core and market.bet_type is BetType.MONEYLINE
    raw = {
        "marketId": "m1",
        "seq": 1061,
        "orders": {
            "buf": [{"price": "0.605", "qty": 38136}, {"price": "0.605", "qty": 25000}],
            "bal": [{"price": "0.325", "qty": 61864}],
        },
    }
    buf, bal = novig.parse_book(market, raw, NOW, 20)
    assert buf.bids == ((D("0.605"), D("631.36")),)
    assert buf.asks == ((D("0.675"), D("618.64")),)  # 1 - 0.325, BAL buyers sell BUF
    assert bal.asks == ((D("0.395"), D("631.36")),)
    assert buf.seq == 1061


async def test_novig_trades_only_when_volume_moves_and_stop_at_checkpoint() -> None:
    calls: list[str] = []
    items = [
        {"tradeId": "t3", "outcomeId": "buf", "price": "0.6", "qty": 100, "ts": 3000},
        {"tradeId": "t2", "outcomeId": "buf", "price": "0.6", "qty": 100, "ts": 2000},
        {"tradeId": "t1", "outcomeId": "buf", "price": "0.6", "qty": 100, "ts": 1000},
    ]

    def handler(r: httpx.Request) -> httpx.Response:
        calls.append(r.url.path)
        return json_response({"items": items})

    adapter = novig.NovigAdapter(mock_http(handler))
    market = novig.parse_market(novig_market(volume=300))

    unchanged = await adapter.fetch_trades([market], {"trades:m1": "300|t3|3000"})
    assert unchanged.trades == [] and calls == []

    batch = await adapter.fetch_trades([market], {"trades:m1": "200|t2|2000"})
    assert [t.trade_key for t in batch.trades] == ["t3"]
    assert batch.trades[0].size == D("1.00")
    assert batch.checkpoints["trades:m1"] == "300|t3|3000"


def test_strip_volatile_keys_keeps_structure() -> None:
    adapter = novig.NovigAdapter(mock_http(lambda r: json_response({})))
    view = adapter.stable_view(
        novig_market(volume=5) | {"outcomes": [{"outcomeId": "x", "bid": {"price": "0.5"}}]}
    )
    assert "volume" not in view and "bid" not in view["outcomes"][0]
    assert json.dumps(view)  # Still serialisable
