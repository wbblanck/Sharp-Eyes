from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from sharp_eyes.history.analyze import (
    F,
    GameRow,
    bh_qvalues,
    load_history,
    parse_payout,
    persistence,
    rank,
    rank_live,
    ratio_t,
    score_event,
    wallet_stats,
    winning_records,
)
from sharp_eyes.history.fetch import HistoryCache, is_game_event, merge_passes
from sharp_eyes.history.report import SharpReport

KICK = 1_790_000_000  # epoch seconds
KICK_ISO = "2026-09-21T14:13:20Z"


def event(eid: str = "1", payout: str = '["1", "0"]', fee_rate: float = 0.0) -> dict[str, Any]:
    return {
        "id": eid,
        "season": "2026",
        "title": "Bears vs. Lions",
        "startTime": KICK_ISO,
        "markets": [
            {
                "conditionId": "0xml",
                "sportsMarketType": "moneyline",
                "outcomes": '["Bears", "Lions"]',
                "outcomePrices": payout,
                "closedTime": "2026-09-21 20:00:00+00",
                "gameStartTime": "2026-09-21 14:13:20+00",
                "feesEnabled": fee_rate > 0,
                "feeSchedule": {"rate": fee_rate, "exponent": 1},
            }
        ],
    }


def fill(ts: int, wallet: str, oi: int, side: str, price: float, size: float, taker: int = 1):
    return [ts, wallet, "0xml", oi, side, price, size, taker]


def closing_tape() -> list[list[Any]]:
    # Market settles Bears around 0.60 in the last 15 minutes.
    return [
        fill(KICK - 600, "mm", 0, "BUY", 0.60, 1000),
        fill(KICK - 60, "mm", 1, "BUY", 0.40, 1000),
    ]


def test_game_event_filter() -> None:
    assert is_game_event({"title": "Bears vs. Lions"})
    assert not is_game_event({"title": "Bears vs. Lions - Player Props"})
    assert not is_game_event({"title": "Super Bowl Champion 2027"})
    match = {"title": "Paris Masters: Jannik Sinner vs Carlos Alcaraz",
             "markets": [{"sportsMarketType": "moneyline"}]}  # fmt: skip
    assert is_game_event(match, "tennis")
    assert not is_game_event({**match, "markets": []}, "tennis")
    assert not is_game_event({"title": "Paris Masters Winner", "markets": []}, "tennis")


def test_live_markout_and_follower_fee() -> None:
    fills = [
        *closing_tape(),
        fill(KICK - 3600, "a", 0, "BUY", 0.50, 100),
        fill(KICK - 3480, "x", 0, "BUY", 0.52, 10),  # copy price 120 s later
        fill(KICK + 600, "a", 0, "BUY", 0.40, 100),  # live bet
        fill(KICK + 720, "x", 0, "BUY", 0.45, 10),  # follower's price
        fill(KICK + 900, "x", 0, "BUY", 0.55, 10),  # 5 min after the bet
        fill(KICK + 1020, "x", 0, "BUY", 0.60, 10),  # 5 min after the copy
    ]
    scored = score_event(event(fee_rate=0.05), fills)
    pre = next(r.sums for r in scored.rows if r.wallet == "a" and r.pregame)
    live = next(r.sums for r in scored.rows if r.wallet == "a" and not r.pregame)
    assert pre[F["copy_fee"]] == pytest.approx(0.05 * 100 * 0.52 * 0.48)
    assert live[F["mark_profit"]] == pytest.approx(100 * (0.55 - 0.40))
    assert live[F["mark_stake"]] == pytest.approx(40)
    assert live[F["lcopy_profit"]] == pytest.approx(100 * (0.60 - 0.45))
    assert live[F["lcopy_fee"]] == pytest.approx(0.05 * 100 * 0.45 * 0.55)


def test_tennis_early_start_moves_the_cutoff() -> None:
    # A 10c swing 20 minutes before the listed start: the match began early,
    # so the bet at -10 minutes is in-play and the close comes from before it.
    ev = {**event(), "sport": "tennis"}
    fills = [
        fill(KICK - 3000, "mm", 0, "BUY", 0.60, 1000),
        fill(KICK - 1200, "mm", 0, "BUY", 0.60, 10),
        fill(KICK - 1100, "mm", 0, "BUY", 0.70, 10),
        fill(KICK - 600, "a", 0, "BUY", 0.65, 100),
    ]
    rows = score_event(ev, fills).rows
    assert not any(r.pregame for r in rows if r.wallet == "a")
    nfl = score_event(event(), fills).rows
    assert any(r.pregame for r in nfl if r.wallet == "a")


def test_payout_requires_a_settled_price() -> None:
    assert parse_payout('["1", "0"]') == (1.0, 0.0)
    assert parse_payout('["0.5", "0.5"]') == (0.5, 0.5)
    assert parse_payout('["0.62", "0.38"]') is None
    assert parse_payout(None) is None


def test_merge_passes_flags_taker_rows() -> None:
    row = {"timestamp": 5, "proxy_wallet": "0xA", "condition_id": "c", "outcome_index": 1,
           "side": "BUY", "price": 0.4, "size": 10, "transaction_hash": "t", "token_id": "k"}  # fmt: skip
    maker = {**row, "proxy_wallet": "0xB", "side": "SELL"}
    merged = merge_passes([row, maker], [row])
    assert merged == [
        [5, "0xa", "c", 1, "BUY", 0.4, 10.0, 1],
        [5, "0xb", "c", 1, "SELL", 0.4, 10.0, 0],
    ]


def test_buy_and_sell_normalise_to_the_same_bet() -> None:
    # Buying Bears at 0.50 and selling Lions at 0.50 are the same wager.
    fills = [
        *closing_tape(),
        fill(KICK - 3600, "a", 0, "BUY", 0.50, 100),
        fill(KICK - 3600, "b", 1, "SELL", 0.50, 100),
    ]
    rows = {r.wallet: r.sums for r in score_event(event(), fills).rows if r.pregame}
    for w in ("a", "b"):
        assert rows[w][F["stake"]] == pytest.approx(50)
        assert rows[w][F["pnl"]] == pytest.approx(50)  # Bears won: 100 x (1 - 0.5)
        assert rows[w][F["clv_profit"]] == pytest.approx(10)  # close 0.60
        assert rows[w][F["tclv_profit"]] == pytest.approx(10)


def test_copy_price_and_live_and_junk_fills() -> None:
    fills = [
        *closing_tape(),
        fill(KICK - 3600, "a", 0, "BUY", 0.50, 100),
        fill(KICK - 3400, "x", 0, "BUY", 0.55, 10),  # first print after a 120 s delay
        fill(KICK + 600, "a", 1, "BUY", 0.30, 100),  # live bet
        fill(KICK + 700, "a", 0, "BUY", 0.99, 1000),  # no information
        fill(KICK + 99999, "a", 0, "BUY", 0.50, 1000),  # after the market closed
    ]
    scored = score_event(event(), fills)
    pre = next(r.sums for r in scored.rows if r.wallet == "a" and r.pregame)
    live = next(r.sums for r in scored.rows if r.wallet == "a" and not r.pregame)
    assert pre[F["copy_profit"]] == pytest.approx(100 * (0.60 - 0.55))
    assert pre[F["copy_stake"]] == pytest.approx(55)
    assert live[F["n"]] == 1
    assert live[F["pnl"]] == pytest.approx(-30)


def test_taker_fee_and_maker_fills() -> None:
    fills = [*closing_tape(), fill(KICK - 3600, "a", 0, "BUY", 0.50, 100, taker=0)]
    sums = next(r.sums for r in score_event(event(fee_rate=0.03), fills).rows if r.wallet == "a")
    assert sums[F["fees"]] == 0
    assert sums[F["tclv_stake"]] == 0  # maker fill: not in the ranking yardstick
    assert sums[F["clv_stake"]] == pytest.approx(50)
    taker = [*closing_tape(), fill(KICK - 3600, "a", 0, "BUY", 0.50, 100)]
    sums = next(r.sums for r in score_event(event(fee_rate=0.03), taker).rows if r.wallet == "a")
    assert sums[F["fees"]] == pytest.approx(0.03 * 100 * 0.25)


def test_ratio_t_is_clustered() -> None:
    r, t = ratio_t([1.0, 1.0, 1.0], [10.0, 10.0, 10.0])
    assert r == pytest.approx(0.1)
    assert t is None  # no variation, no t
    r, t = ratio_t([2.0, 0.0, 1.0, 1.0], [10.0, 10.0, 10.0, 10.0])
    assert r == pytest.approx(0.1)
    assert t is not None and t > 0


def test_bh_qvalues() -> None:
    q = bh_qvalues([0.01, 0.04, 0.03, 0.5])
    assert q == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.5])


def _rows(wallet: str, edge: float, games: range) -> list[GameRow]:
    rows = []
    for g in games:
        sums = [0.0] * len(F)
        noise = 0.01 * math.sin(g * 7.0 + len(wallet))
        sums[F["stake"]] = sums[F["clv_stake"]] = sums[F["tclv_stake"]] = 100.0
        sums[F["taker_stake"]] = 100.0
        sums[F["clv_profit"]] = sums[F["tclv_profit"]] = 100.0 * (edge + noise)
        sums[F["pnl"]] = 100.0 * edge
        rows.append(GameRow(wallet, str(g), float(g), True, sums))
    return rows


def test_rank_and_persistence_separate_skill() -> None:
    rows = [r for i in range(10) for r in _rows(f"dud{i}", -0.01, range(60))]
    rows += _rows("sharp", 0.03, range(60))
    ranked = rank(wallet_stats(rows), min_games=20, min_stake=100)
    assert ranked[0].wallet == "sharp" and ranked[0].sharp
    assert not any(s.sharp for s in ranked[1:])
    check = persistence(rows, 30.0, min_games=20, min_stake=100, top_n=1)
    top = check.groups[1]
    assert top.wallets == 1 and top.taker_clv is not None and top.taker_clv > 0.02


def test_rank_live_flags_fast_bettors() -> None:
    rows = []
    for wallet, edge in [*((f"dud{i}", -0.005) for i in range(10)), ("fast", 0.03)]:
        for r in _rows(wallet, 0.0, range(40)):
            r.pregame = False
            noise = 0.01 * math.sin(int(r.event_id) * 3.0 + len(wallet))
            r.sums[F["mark_stake"]] = 100.0
            r.sums[F["mark_profit"]] = 100.0 * (edge + noise)
            rows.append(r)
    ranked = rank_live(wallet_stats(rows), min_games=20, min_stake=100)
    assert ranked[0].wallet == "fast" and ranked[0].live_sharp
    assert not any(s.live_sharp for s in ranked[1:])


def test_cache_round_trip_and_report(tmp_path: Path) -> None:
    cache = HistoryCache(tmp_path)
    fills = [*closing_tape(), fill(KICK - 3600, "a", 0, "BUY", 0.50, 100)]
    cache.save(event("7"), fills)
    assert cache.event_ids() == ["7"]
    history = load_history(cache)
    assert history.games == 1 and history.fills == 3
    ranked = rank(wallet_stats(history.rows, history.by_type), min_games=1, min_stake=1)
    report = SharpReport(history, ranked, None, 1, 1, 120)
    assert "Sharp NFL traders" in report.to_markdown()
    assert report.to_csv().count("\n") == len(ranked) + 1


def test_win_rate_counts_net_positions_per_market() -> None:
    # Two fills on the winning side of one market are one winning bet.
    fills = [
        *closing_tape(),
        fill(KICK - 3600, "a", 0, "BUY", 0.50, 100),
        fill(KICK - 3000, "a", 0, "BUY", 0.52, 100),
        fill(KICK - 3600, "b", 1, "BUY", 0.50, 100),
    ]
    rows = {r.wallet: r.sums for r in score_event(event(), fills).rows if r.pregame}
    assert rows["a"][F["bets"]] == 1 and rows["a"][F["wins"]] == 1
    assert rows["b"][F["bets"]] == 1 and rows["b"][F["wins"]] == 0


def test_winning_records_need_profit_and_win_rate() -> None:
    rows = _rows("winner", 0.02, range(30)) + _rows("loser", -0.02, range(30))
    for r in rows:
        r.sums[F["bets"]] = 1
        r.sums[F["wins"]] = 1 if r.wallet == "winner" and int(r.event_id) % 3 else 0
    picked = winning_records(wallet_stats(rows), min_games=20, min_stake=100)
    assert [s.wallet for s in picked] == ["winner"]
    assert picked[0].win_rate == pytest.approx(20 / 30)
