"""Copyability report over captured data: ``sharp-eyes copyability-report``."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine

from sharp_eyes.capture.records import CaptureVenue
from sharp_eyes.config import AppConfig
from sharp_eyes.copyability.score import CopyScore, Verdict, score_wager
from sharp_eyes.copyability.store import CaptureQuotes, load_catalog, load_source_fills
from sharp_eyes.copyability.wagers import aggregate_wagers
from sharp_eyes.matching.nfl import MATCHER_VERSION, OptionIndex, Side
from sharp_eyes.taxonomy.templates import TEMPLATE_SET_VERSION


@dataclass
class CopyabilityReport:
    generated_at: str
    window_start: str
    window_end: str
    settings: dict[str, Any]
    fills_live: int
    fills_backfilled_excluded: int
    wagers_total: int
    wagers_in_scope: int
    verdicts: dict[str, int]
    catalog_options: dict[str, int]
    catalog_unresolved: list[tuple[str, int]]
    scored: dict[str, Any] = field(default_factory=dict)
    reasons: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    wallets: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    def to_markdown(self) -> str:
        s = self.scored
        lines = [
            "# Copyability of Polymarket NFL wagers",
            "",
            f"Window: {self.window_start} to {self.window_end} (UTC, block time). "
            f"Matcher {MATCHER_VERSION}, settlement templates {TEMPLATE_SET_VERSION}.",
            "",
            "Each wager is a wallet's run of BUY fills on one outcome. A follower acts "
            f"{self.settings['reaction_seconds']} s after we first saw it, buying "
            f"${self.settings['stake_usd']} on Polymarket US, Kalshi or Novig at the best "
            "fee-inclusive price in the captured book. Pre-game NFL moneyline, spread and "
            "total only. Prices in cents per $1 contract.",
            "",
            f"* Live-detected fills: {self.fills_live:,} "
            f"(backfilled fills excluded: {self.fills_backfilled_excluded:,})",
            f"* Wagers: {self.wagers_total:,}; at least "
            f"${self.settings['min_notional_usd']} notional: {self.wagers_in_scope:,}",
            "* Outcome: " + ", ".join(f"{k} {v:,}" for k, v in self.verdicts.items()),
            "",
        ]
        if s:
            lines += [
                "## Scored wagers",
                "",
                "| measure | n | mean | median | share > 0 |",
                "|---|---|---|---|---|",
            ]
            for name in (
                "slippage",
                "slippage_with_fees",
                "follower_clv",
                "trader_clv",
                "copy_cost",
            ):
                d = s.get(name) or {}
                lines.append(
                    f"| {name} | {d.get('n', 0)} | {_c(d.get('mean'))} | {_c(d.get('median'))} "
                    f"| {_pct(d.get('share_positive'))} |"
                )
            lines += [
                "",
                "slippage = follower average price minus trader price; slippage_with_fees adds "
                "the follower's taker fee per contract; follower_clv = closing "
                "mid minus follower price with fees; trader_clv = Polymarket closing mid minus "
                "trader price; copy_cost = trader_clv minus follower_clv.",
                "",
                "Best venue: " + ", ".join(f"{k} {v}" for k, v in s.get("best_venue", {}).items()),
                "",
                "Match state of the chosen contract: "
                + ", ".join(f"{k} {v}" for k, v in s.get("match_state", {}).items()),
                "",
                "Quote staleness bound (capture tier interval): "
                + ", ".join(f"{k} s: {v}" for k, v in s.get("age_bound", {}).items()),
                "",
                f"Detection delay (first fill block time to first observation): median "
                f"{_n(s.get('detection_p50'))} s, p90 {_n(s.get('detection_p90'))} s.",
                "",
            ]
        for verdict, rows in self.reasons.items():
            if rows:
                lines += [f"## Why {verdict}", ""]
                lines += [f"* {reason}: {n:,}" for reason, n in rows]
                lines.append("")
        if self.wallets:
            lines += [
                "## Wallets with the most scored wagers",
                "",
                "| wallet | scored | mean follower CLV | mean trader CLV | mean slippage |",
                "|---|---|---|---|---|",
            ]
            for w in self.wallets:
                lines.append(
                    f"| `{w['wallet']}` | {w['n']} | {_c(w['follower_clv'])} "
                    f"| {_c(w['trader_clv'])} | {_c(w['slippage'])} |"
                )
            lines += [
                "",
                "A handful of wagers says nothing about skill; this table is for spotting "
                "wallets worth studying, not for qualification.",
                "",
            ]
        lines += [
            "## Catalog coverage",
            "",
            "Buy options per venue: "
            + ", ".join(f"{k} {v:,}" for k, v in self.catalog_options.items()),
            "",
        ]
        if self.catalog_unresolved:
            lines += ["Listings not resolved:", ""]
            lines += [f"* {r}: {n:,}" for r, n in self.catalog_unresolved]
            lines.append("")
        return "\n".join(lines)


def build_report(
    engine: Engine,
    config: AppConfig,
    start: datetime,
    end: datetime,
    *,
    now: datetime | None = None,
) -> CopyabilityReport:
    settings = config.copyability.settings(config.paper.stake_usd())
    now = now or datetime.now(UTC)
    events, markets = load_catalog(engine, start - timedelta(days=8), end + timedelta(days=8))
    index = OptionIndex.build(events, markets)
    fills, backfilled = load_source_fills(engine, start, end)
    wagers = aggregate_wagers(fills, config.copyability.wager_window_seconds)
    min_notional = config.copyability.min_notional_usd
    mapped = [
        w for w in wagers
        if w.notional >= min_notional and index.option(CaptureVenue.POLYMARKET, w.book_key)
    ]  # fmt: skip
    quotes = CaptureQuotes(engine, config.capture)
    scores = [score_wager(w, index, quotes, settings, now=now) for w in mapped]
    verdicts = Counter(s.verdict.value for s in scores)
    unresolved = Counter(f"{u.venue.value}: {u.reason[:90]}" for u in index.unresolved)
    return CopyabilityReport(
        generated_at=now.isoformat(timespec="seconds"),
        window_start=start.isoformat(timespec="seconds"),
        window_end=end.isoformat(timespec="seconds"),
        settings={
            "stake_usd": str(settings.stake_usd),
            "reaction_seconds": settings.reaction_seconds,
            "max_quote_age_seconds": settings.max_quote_age_seconds,
            "accept_states": [s.value for s in settings.accept_states],
            "min_notional_usd": str(min_notional),
            "wager_window_seconds": config.copyability.wager_window_seconds,
        },
        fills_live=len(fills),
        fills_backfilled_excluded=backfilled,
        wagers_total=len(wagers),
        wagers_in_scope=len(mapped),
        verdicts=dict(verdicts.most_common()),
        catalog_options=dict(Counter(o.venue.value for o in index.options).most_common()),
        catalog_unresolved=unresolved.most_common(10),
        scored=_scored_summary([s for s in scores if s.verdict is Verdict.SCORED]),
        reasons={
            v.value: Counter(s.reason or "" for s in scores if s.verdict is v).most_common(10)
            for v in (Verdict.UNSCORABLE, Verdict.NO_MATCH)
        },
        wallets=_wallets([s for s in scores if s.verdict is Verdict.SCORED]),
    )


def _stats(values: Sequence[Decimal]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    floats = [float(v) for v in values]
    return {
        "n": len(floats),
        "mean": statistics.fmean(floats),
        "median": statistics.median(floats),
        "share_positive": sum(1 for v in floats if v > 0) / len(floats),
    }


def _scored_summary(scores: Sequence[CopyScore]) -> dict[str, Any]:
    if not scores:
        return {}
    both = [s for s in scores if s.follower_clv is not None and s.trader_clv is not None]
    detection = sorted(s.detection_seconds for s in scores if s.detection_seconds is not None)
    best = [s.best for s in scores if s.best]
    return {
        "slippage": _stats([s.slippage for s in scores if s.slippage is not None]),
        "slippage_with_fees": _stats(
            [s.best.fill.effective_price - s.wager.price for s in scores if s.best and s.best.fill]
        ),
        "follower_clv": _stats([s.follower_clv for s in scores if s.follower_clv is not None]),
        "trader_clv": _stats([s.trader_clv for s in scores if s.trader_clv is not None]),
        "copy_cost": _stats([s.trader_clv - s.follower_clv for s in both]),  # type: ignore[operator]
        "best_venue": dict(Counter(b.option.venue.value for b in best).most_common()),
        "match_state": dict(Counter(b.state.value for b in best).most_common()),
        "short_side": sum(1 for b in best if b.option.side is Side.SHORT),
        "age_bound": dict(sorted(Counter(b.age_bound_seconds or 0 for b in best).items())),
        "detection_p50": _quantile(detection, 0.5),
        "detection_p90": _quantile(detection, 0.9),
    }


def _wallets(scores: Sequence[CopyScore], top: int = 15) -> list[dict[str, Any]]:
    by_wallet: dict[str, list[CopyScore]] = defaultdict(list)
    for s in scores:
        by_wallet[s.wager.wallet].append(s)

    def mean(values: list[Decimal | None]) -> float | None:
        known = [float(v) for v in values if v is not None]
        return statistics.fmean(known) if known else None

    rows: list[dict[str, Any]] = [
        {
            "wallet": wallet,
            "n": len(items),
            "follower_clv": mean([s.follower_clv for s in items]),
            "trader_clv": mean([s.trader_clv for s in items]),
            "slippage": mean([s.slippage for s in items]),
        }
        for wallet, items in by_wallet.items()
    ]
    rows.sort(key=lambda r: (-r["n"], r["wallet"]))
    return rows[:top]


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    return values[min(len(values) - 1, int(q * len(values)))]


def _c(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.2f}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _n(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f}"
