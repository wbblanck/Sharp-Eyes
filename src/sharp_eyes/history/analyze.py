"""Score every wallet's NFL wagers on skill versus luck, from cached history.

Each fill is normalised to "bought outcome k at price q for s shares": a BUY
of outcome i is (i, p); a SELL of outcome i at p is economically a buy of the
other outcome at 1 - p. Three yardsticks per wager, all as profit per dollar
staked so they share units:

* **ROI**: settled result, ``s * (payout_k - q)`` minus taker fees. Honest but
  noisy: an NFL side is close to a coin flip.
* **CLV** (closing-line value), pre-game only: ``s * (close_k - q)``, where
  the close is the volume-weighted price in the last 15 minutes before
  kickoff. Beating the close is the standard, much less noisy skill signal.
* **Copy CLV**: the same, but at the first price printed ``copy_delay``
  seconds after the wager, i.e. what a follower detecting the trade late
  would have paid. This is the edge left to copy.

Wallets are ranked on CLV of their taker fills alone (see :func:`rank`).

Significance is a t-statistic of the stake-weighted ratio, clustered by game
(a wallet's fills on one game are not independent). With thousands of
wallets some clear t = 3 by luck, so p-values get a Benjamini-Hochberg
correction, and the ``persistence`` check ranks wallets on one period and
measures them on the next, which luck cannot pass.
"""

from __future__ import annotations

import bisect
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sharp_eyes.capture.records import BetType, Period
from sharp_eyes.capture.venues.base import classify
from sharp_eyes.capture.venues.polymarket import MARKET_TYPES
from sharp_eyes.history.fetch import HistoryCache

CLOSE_WINDOW = 15 * 60  # seconds before kickoff averaged into the closing price
CLOSE_MIN_NOTIONAL = 100.0  # below this, fall back to the last few trades
CLOSE_FALLBACK_TRADES = 5
CLOSE_FALLBACK_AGE = 6 * 3600
COPY_MAX_WAIT = 30 * 60  # no print within this long after the delay: no copy price
PRICE_FLOOR, PRICE_CAP = 0.03, 0.97  # outside: near-certain outcomes, no information


def parse_ts(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip().replace(" ", "T").replace("Z", "+00:00")
    if text.endswith("+00"):
        text += ":00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


@dataclass(frozen=True)
class MarketInfo:
    condition_id: str
    bet_type: BetType
    period: Period
    kickoff: float
    closed_at: float | None
    payout: tuple[float, float]
    fee_rate: float
    fee_exponent: float


def parse_payout(raw: Any) -> tuple[float, float] | None:
    try:
        vals = [float(x) for x in json.loads(raw)] if isinstance(raw, str) else None
    except (TypeError, ValueError):
        return None
    if not vals or len(vals) != 2 or abs(sum(vals) - 1) > 1e-6:
        return None
    if any(v not in (0.0, 0.5, 1.0) for v in vals):
        return None  # not settled (still a live price)
    return vals[0], vals[1]


def parse_markets(event: dict[str, Any]) -> dict[str, MarketInfo]:
    event_start = parse_ts(event.get("startTime"))
    out = {}
    for m in event.get("markets") or []:
        payout = parse_payout(m.get("outcomePrices"))
        kickoff = parse_ts(m.get("gameStartTime")) or event_start
        if payout is None or kickoff is None or not m.get("conditionId"):
            continue
        bet_type, period = classify(MARKET_TYPES, m.get("sportsMarketType") or "")
        fees = m.get("feeSchedule") or {}
        rate = float(fees.get("rate") or 0) if m.get("feesEnabled") else 0.0
        out[m["conditionId"]] = MarketInfo(
            condition_id=m["conditionId"],
            bet_type=bet_type,
            period=period,
            kickoff=kickoff,
            closed_at=parse_ts(m.get("closedTime")),
            payout=payout,
            fee_rate=rate,
            fee_exponent=float(fees.get("exponent") or 1),
        )
    return out


@dataclass
class PricePath:
    """Outcome-0 prices of one market's taker prints, in time order."""

    ts: list[float] = field(default_factory=list)
    p0: list[float] = field(default_factory=list)
    notional: list[float] = field(default_factory=list)

    def close(self, kickoff: float) -> float | None:
        end = bisect.bisect_left(self.ts, kickoff)
        start = bisect.bisect_left(self.ts, kickoff - CLOSE_WINDOW)
        num = sum(self.p0[i] * self.notional[i] for i in range(start, end))
        den = sum(self.notional[i] for i in range(start, end))
        if den >= CLOSE_MIN_NOTIONAL:
            return num / den
        recent = [
            i
            for i in range(max(0, end - CLOSE_FALLBACK_TRADES), end)
            if self.ts[i] >= kickoff - CLOSE_FALLBACK_AGE
        ]
        if not recent:
            return None
        return sum(self.p0[i] for i in recent) / len(recent)

    def price_after(self, t: float, before: float) -> float | None:
        i = bisect.bisect_left(self.ts, t)
        if i < len(self.ts) and self.ts[i] < before and self.ts[i] <= t + COPY_MAX_WAIT:
            return self.p0[i]
        return None


def price_paths(fills: Iterable[Sequence[Any]]) -> dict[str, PricePath]:
    paths: dict[str, PricePath] = defaultdict(PricePath)
    for ts, _w, cid, oi, _side, price, size, taker in sorted(fills, key=lambda f: f[0]):
        if not taker or not PRICE_FLOOR <= price <= PRICE_CAP:
            continue
        path = paths[cid]
        path.ts.append(ts)
        path.p0.append(price if oi == 0 else 1 - price)
        path.notional.append(size * price)
    return paths


# Per (wallet, game, phase) sums. Index names for the row list below.
FIELDS = (
    "n",
    "stake",
    "pnl",
    "fees",
    "taker_stake",
    "clv_profit",
    "clv_stake",
    "copy_profit",
    "copy_stake",
    "copy_pnl",
    "tclv_profit",
    "tclv_stake",
)
F = {name: i for i, name in enumerate(FIELDS)}


@dataclass
class GameRow:
    wallet: str
    event_id: str
    kickoff: float
    pregame: bool
    sums: list[float]


@dataclass
class EventScore:
    rows: list[GameRow]
    # (wallet, bet type) -> [pregame stake, clv profit, clv stake]
    by_bet_type: dict[tuple[str, str], list[float]]


def score_event(
    event: dict[str, Any], fills: Sequence[Sequence[Any]], copy_delay: float = 120.0
) -> EventScore:
    markets = parse_markets(event)
    paths = price_paths(fills)
    closes = {cid: paths[cid].close(m.kickoff) if cid in paths else None
              for cid, m in markets.items()}  # fmt: skip
    acc: dict[tuple[str, bool], list[float]] = defaultdict(lambda: [0.0] * len(FIELDS))
    by_type: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    kickoff = min((m.kickoff for m in markets.values()), default=0.0)
    for ts, wallet, cid, oi, side, price, size, taker in fills:
        m = markets.get(cid)
        if m is None or not wallet or not PRICE_FLOOR <= price <= PRICE_CAP:
            continue
        if m.closed_at is not None and ts >= m.closed_at:
            continue
        k = oi if side == "BUY" else 1 - oi
        q = price if side == "BUY" else 1 - price
        stake = size * q
        fee = m.fee_rate * size * (price * (1 - price)) ** m.fee_exponent if taker else 0.0
        pnl = size * (m.payout[k] - q) - fee
        pregame = ts < m.kickoff
        a = acc[(wallet, pregame)]
        a[F["n"]] += 1
        a[F["stake"]] += stake
        a[F["pnl"]] += pnl
        a[F["fees"]] += fee
        if taker:
            a[F["taker_stake"]] += stake
        if not pregame:
            continue
        close0 = closes.get(cid)
        bt = by_type[(wallet, m.bet_type.value)]
        bt[0] += stake
        if close0 is None:
            continue
        close_k = close0 if k == 0 else 1 - close0
        a[F["clv_profit"]] += size * (close_k - q)
        a[F["clv_stake"]] += stake
        if taker:
            a[F["tclv_profit"]] += size * (close_k - q)
            a[F["tclv_stake"]] += stake
        bt[1] += size * (close_k - q)
        bt[2] += stake
        p_after = paths[cid].price_after(ts + copy_delay, m.kickoff) if cid in paths else None
        if p_after is not None:
            copy_q = p_after if k == 0 else 1 - p_after
            if PRICE_FLOOR <= copy_q <= PRICE_CAP:
                a[F["copy_profit"]] += size * (close_k - copy_q)
                a[F["copy_stake"]] += size * copy_q
                a[F["copy_pnl"]] += size * (m.payout[k] - copy_q)
    rows = [
        GameRow(wallet, str(event["id"]), kickoff, pregame, sums)
        for (wallet, pregame), sums in acc.items()
    ]
    return EventScore(rows, dict(by_type))


def ratio_t(xs: Sequence[float], ys: Sequence[float]) -> tuple[float | None, float | None]:
    """Ratio sum(x)/sum(y) and its t-statistic, clustered by observation."""
    sy = sum(ys)
    n = len(xs)
    if sy <= 0:
        return None, None
    r = sum(xs) / sy
    if n < 2:
        return r, None
    resid = sum((x - r * y) ** 2 for x, y in zip(xs, ys, strict=True))
    var = n / (n - 1) * resid / sy**2
    if var <= 0:
        return r, None
    return r, r / math.sqrt(var)


def one_sided_p(t: float | None) -> float:
    if t is None:
        return 1.0
    return 0.5 * math.erfc(t / math.sqrt(2))


def bh_qvalues(pvalues: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg q-values, in input order."""
    n = len(pvalues)
    order = sorted(range(n), key=lambda i: pvalues[i])
    q = [1.0] * n
    running = 1.0
    for rank in range(n, 0, -1):
        i = order[rank - 1]
        running = min(running, pvalues[i] * n / rank)
        q[i] = running
    return q


@dataclass
class WalletStats:
    wallet: str
    games: int  # games with pre-game action
    pre_stake: float
    pre_pnl: float
    roi: float | None
    roi_t: float | None
    taker_games: int  # games with pre-game taker bets that have a closing price
    taker_clv: float | None
    taker_clv_t: float | None
    clv: float | None
    clv_t: float | None
    copy_clv: float | None
    copy_clv_t: float | None
    copy_roi: float | None
    live_games: int
    live_stake: float
    live_pnl: float
    maker_share: float
    first: float
    last: float
    q_value: float = 1.0
    bet_types: dict[str, tuple[float, float | None]] = field(default_factory=dict)

    @property
    def sharp(self) -> bool:
        return self.q_value < 0.05 and (self.taker_clv or 0) > 0

    @property
    def copyable(self) -> bool:
        return self.sharp and (self.copy_clv_t or 0) >= 2


def wallet_stats(
    rows: Iterable[GameRow], by_type: dict[tuple[str, str], list[float]] | None = None
) -> list[WalletStats]:
    per: dict[str, list[GameRow]] = defaultdict(list)
    for r in rows:
        per[r.wallet].append(r)
    by_type = by_type or {}
    types_of: dict[str, dict[str, tuple[float, float | None]]] = defaultdict(dict)
    for (wallet, bt), (stake, clv_p, clv_s) in by_type.items():
        types_of[wallet][bt] = (stake, clv_p / clv_s if clv_s > 0 else None)
    out = []
    for wallet, grs in per.items():
        pre = [g.sums for g in grs if g.pregame and g.sums[F["stake"]] > 0]
        live = [g.sums for g in grs if not g.pregame and g.sums[F["stake"]] > 0]

        def col(group: list[list[float]], name: str) -> list[float]:
            return [s[F[name]] for s in group]

        roi, roi_t = ratio_t(col(pre, "pnl"), col(pre, "stake"))
        clv, clv_t = ratio_t(col(pre, "clv_profit"), col(pre, "clv_stake"))
        tpre = [s for s in pre if s[F["tclv_stake"]] > 0]
        tclv, tclv_t = ratio_t(col(tpre, "tclv_profit"), col(tpre, "tclv_stake"))
        copy_clv, copy_t = ratio_t(col(pre, "copy_profit"), col(pre, "copy_stake"))
        copy_roi, _ = ratio_t(col(pre, "copy_pnl"), col(pre, "copy_stake"))
        stake_all = sum(g.sums[F["stake"]] for g in grs)
        taker_all = sum(g.sums[F["taker_stake"]] for g in grs)
        out.append(
            WalletStats(
                wallet=wallet,
                games=len(pre),
                pre_stake=sum(col(pre, "stake")),
                pre_pnl=sum(col(pre, "pnl")),
                roi=roi,
                roi_t=roi_t,
                taker_games=len(tpre),
                taker_clv=tclv,
                taker_clv_t=tclv_t,
                clv=clv,
                clv_t=clv_t,
                copy_clv=copy_clv,
                copy_clv_t=copy_t,
                copy_roi=copy_roi,
                live_games=len(live),
                live_stake=sum(col(live, "stake")),
                live_pnl=sum(col(live, "pnl")),
                maker_share=1 - taker_all / stake_all if stake_all > 0 else 0.0,
                first=min(g.kickoff for g in grs),
                last=max(g.kickoff for g in grs),
                bet_types=types_of.get(wallet, {}),
            )
        )
    return out


def rank(
    stats: Sequence[WalletStats], *, min_games: int = 20, min_stake: float = 2000.0
) -> list[WalletStats]:
    """Eligible wallets by taker CLV t-statistic, with BH q-values set across them.

    Only taker (aggressive) fills count toward the rank: they state a view and
    pay the ask, while a resting order filled at the bid beats a mid-ish close
    by half the spread without any opinion on the game.
    """
    eligible = [s for s in stats if s.taker_games >= min_games and s.pre_stake >= min_stake]
    qs = bh_qvalues([one_sided_p(s.taker_clv_t) for s in eligible])
    for s, q in zip(eligible, qs, strict=True):
        s.q_value = q
    return sorted(
        eligible,
        key=lambda s: s.taker_clv_t if s.taker_clv_t is not None else -1e9,
        reverse=True,
    )


@dataclass
class History:
    rows: list[GameRow]
    by_type: dict[tuple[str, str], list[float]]
    games: int
    fills: int
    first: float
    last: float


def load_history(cache: HistoryCache, *, copy_delay: float = 120.0) -> History:
    rows: list[GameRow] = []
    by_type: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    games = fills_n = 0
    first, last = math.inf, -math.inf
    for eid in cache.event_ids():
        event = cache.load_event(eid)
        fills = cache.load_fills(eid)
        scored = score_event(event, fills, copy_delay)
        if not scored.rows:
            continue
        games += 1
        fills_n += len(fills)
        rows.extend(scored.rows)
        for key, vals in scored.by_bet_type.items():
            agg = by_type[key]
            for i, v in enumerate(vals):
                agg[i] += v
        first = min(first, scored.rows[0].kickoff)
        last = max(last, scored.rows[0].kickoff)
    return History(rows, dict(by_type), games, fills_n, first, last)


@dataclass
class GroupResult:
    label: str
    wallets: int
    games: int
    stake: float
    taker_clv: float | None
    clv: float | None
    roi: float | None
    copy_clv: float | None


@dataclass
class Persistence:
    split: float
    train_games: int
    test_games: int
    groups: list[GroupResult]
    rank_corr: float | None
    compared: int


def _pooled(label: str, rows: Sequence[GameRow], wallets: set[str]) -> GroupResult:
    pre = [r.sums for r in rows if r.pregame and r.wallet in wallets and r.sums[F["stake"]] > 0]
    games = {(r.wallet, r.event_id) for r in rows if r.pregame and r.wallet in wallets}

    def ratio(x: str, y: str) -> float | None:
        den = sum(s[F[y]] for s in pre)
        return sum(s[F[x]] for s in pre) / den if den > 0 else None

    return GroupResult(
        label=label,
        wallets=len({r.wallet for r in rows if r.pregame and r.wallet in wallets}),
        games=len(games),
        stake=sum(s[F["stake"]] for s in pre),
        taker_clv=ratio("tclv_profit", "tclv_stake"),
        clv=ratio("clv_profit", "clv_stake"),
        roi=ratio("pnl", "stake"),
        copy_clv=ratio("copy_profit", "copy_stake"),
    )


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None

    def ranks(v: Sequence[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: v[i])
        out = [0.0] * n
        for r, i in enumerate(order):
            out[i] = float(r)
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    return cov / math.sqrt(vx * vy) if vx > 0 and vy > 0 else None


def persistence(
    rows: Sequence[GameRow],
    split: float,
    *,
    min_games: int = 20,
    min_stake: float = 2000.0,
    min_test_games: int = 5,
    top_n: int = 25,
) -> Persistence:
    """Rank on games before ``split``, then measure the same wallets after it."""
    train = [r for r in rows if r.kickoff < split]
    test = [r for r in rows if r.kickoff >= split]
    ranked = rank(wallet_stats(train), min_games=min_games, min_stake=min_stake)
    sharp = {s.wallet for s in ranked if s.sharp}
    top = {s.wallet for s in ranked[:top_n]}
    bottom = {s.wallet for s in ranked[-top_n:]}
    everyone = {r.wallet for r in test}
    groups = [
        _pooled(f"Flagged sharp before split (q < 0.05, {len(sharp)} wallets)", test, sharp),
        _pooled(f"Top {top_n} before split", test, top),
        _pooled(f"Bottom {top_n} before split", test, bottom),
        _pooled("Every wallet", test, everyone),
    ]
    test_stats = {s.wallet: s for s in wallet_stats(test)}
    pairs = [
        (s.taker_clv_t, test_stats[s.wallet].taker_clv)
        for s in ranked
        if s.taker_clv_t is not None
        and s.wallet in test_stats
        and test_stats[s.wallet].taker_games >= min_test_games
        and test_stats[s.wallet].taker_clv is not None
    ]
    corr = spearman([p[0] for p in pairs], [p[1] for p in pairs])  # type: ignore[misc]
    return Persistence(
        split=split,
        train_games=len({r.event_id for r in train}),
        test_games=len({r.event_id for r in test}),
        groups=groups,
        rank_corr=corr,
        compared=len(pairs),
    )
