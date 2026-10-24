"""Copyability of one source wager (audit recommendation 2).

A trader's own price is not what a follower gets. For each wager this module
asks: when our system first saw it, plus a reaction delay, what could a
follower actually have bought on an eligible execution venue, for the paper
stake, walking the captured book, after taker fees? And how did that price
compare with the closing line?

Measures, all in probability points (0.01 = one cent per $1 contract):

* ``slippage``: follower average fill price minus the trader's price. The cost
  of arriving later and elsewhere, including other copy traders moving first.
* ``follower_clv``: closing mid minus the follower's fee-inclusive price.
  Positive means the follower beat the close.
* ``trader_clv``: closing mid on Polymarket minus the trader's price. A skill
  signal for the trader, not evidence of copyability.

A wager is UNSCORABLE whenever the evidence is missing (no captured book near
the follow time, a polling gap, a stale tier) rather than falling back to the
trader's price. In-play wagers are recorded but not scored in v1 (audit
recommendation 4).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from sharp_eyes.capture.records import CaptureVenue, Level
from sharp_eyes.copyability.fill import DEFAULT_LOTS, SimFill, buy_levels, mid, simulate_buy
from sharp_eyes.copyability.wagers import Wager
from sharp_eyes.domain import MatchState
from sharp_eyes.matching.nfl import BuyOption, OptionIndex, Side, classify_match
from sharp_eyes.pricing.fees import FeeModelError, fee_model


class Timing(StrEnum):
    PRE_GAME = "PRE_GAME"
    IN_PLAY = "IN_PLAY"


class Verdict(StrEnum):
    SCORED = "SCORED"
    UNSCORABLE = "UNSCORABLE"  # Matched, but no usable captured price
    NO_MATCH = "NO_MATCH"  # No eligible equivalent contract on an execution venue
    NOT_MAPPED = "NOT_MAPPED"  # The source listing itself was not resolved
    IN_PLAY = "IN_PLAY"  # Research only in v1


@dataclass(frozen=True)
class BookView:
    bids: tuple[Level, ...]
    asks: tuple[Level, ...]
    observed_at: datetime


@dataclass(frozen=True)
class BookLookup:
    book: BookView | None
    problem: str | None = None
    # Longest the venue could have gone unpolled for this book at that time
    # (the capture tier interval): the quote's worst-case staleness.
    age_bound_seconds: int | None = None


class QuoteSource(Protocol):
    def book_at(
        self, venue: CaptureVenue, book_key: str, at: datetime, kickoff: datetime | None
    ) -> BookLookup:
        """The book as a follower would have seen it at ``at``, or why that is unknown."""

    def closing_book(
        self, venue: CaptureVenue, book_key: str, kickoff: datetime
    ) -> BookView | None:
        """The last captured book before kickoff."""


@dataclass(frozen=True)
class CopyabilitySettings:
    stake_usd: Decimal = Decimal("10")
    reaction_seconds: float = 5.0
    max_quote_age_seconds: int = 600
    target_venues: tuple[CaptureVenue, ...] = (
        CaptureVenue.POLYMARKET_US,
        CaptureVenue.KALSHI,
        CaptureVenue.NOVIG,
    )
    accept_states: tuple[MatchState, ...] = (
        MatchState.EXACT,
        MatchState.EQUIVALENT_WITH_RULE_DIFFERENCE,
    )
    require_complete_fill: bool = True


@dataclass(frozen=True)
class VenueQuote:
    option: BuyOption
    state: MatchState
    differences: tuple[str, ...]
    fill: SimFill | None = None
    problem: str | None = None
    book_observed_at: datetime | None = None
    age_bound_seconds: int | None = None


@dataclass(frozen=True)
class CopyScore:
    wager: Wager
    verdict: Verdict
    timing: Timing | None = None
    follow_at: datetime | None = None
    reason: str | None = None
    best: VenueQuote | None = None
    quotes: tuple[VenueQuote, ...] = field(default=())
    slippage: Decimal | None = None
    follower_clv: Decimal | None = None
    trader_clv: Decimal | None = None
    detection_seconds: float | None = None

    @property
    def proposition(self) -> str | None:
        return str(self.best.option.proposition) if self.best else None


def score_wager(
    wager: Wager,
    index: OptionIndex,
    quotes: QuoteSource,
    settings: CopyabilitySettings,
    *,
    now: datetime | None = None,
) -> CopyScore:
    source = index.option(CaptureVenue.POLYMARKET, wager.book_key, Side.LONG)
    if source is None:
        return CopyScore(wager, Verdict.NOT_MAPPED, reason="source listing not resolved")
    kickoff = source.kickoff
    detection = (wager.detected_at - wager.first_ts).total_seconds()
    follow_at = wager.detected_at + timedelta(seconds=settings.reaction_seconds)
    timing = Timing.PRE_GAME if kickoff is None or wager.last_ts < kickoff else Timing.IN_PLAY
    head = CopyScore(
        wager, Verdict.UNSCORABLE, timing=timing, follow_at=follow_at, detection_seconds=detection
    )
    if kickoff is None:
        return replace(head, reason="no kickoff time")
    if timing is Timing.IN_PLAY:
        return replace(head, verdict=Verdict.IN_PLAY, reason="in-play wagers are research only")
    if follow_at >= kickoff:
        return replace(head, reason="detected after kickoff")

    candidates = []
    for opt in index.equivalents(source.proposition):
        if opt.venue not in settings.target_venues:
            continue
        state, diffs = classify_match(source.rules, opt.rules)
        candidates.append((opt, state, tuple(diffs)))
    accepted = [c for c in candidates if c[1] in settings.accept_states]
    if not accepted:
        why = (
            "no listing on an execution venue"
            if not candidates
            else "only " + ", ".join(sorted({c[1].value for c in candidates})) + " matches"
        )
        return replace(head, verdict=Verdict.NO_MATCH, reason=why)

    results = [
        _quote(opt, state, diffs, quotes, settings, follow_at, kickoff)
        for opt, state, diffs in accepted
    ]
    usable = [
        q for q in results
        if q.fill is not None and (q.fill.complete or not settings.require_complete_fill)
    ]  # fmt: skip
    if not usable:
        problems = sorted({q.problem or "book too thin for the stake" for q in results})
        return replace(head, reason="; ".join(problems), quotes=tuple(results))
    best = min(usable, key=_cost)
    assert best.fill is not None

    follower_clv = trader_clv = None
    if now is None or now >= kickoff:
        close = quotes.closing_book(best.option.venue, best.option.book_key, kickoff)
        if close and (m := mid(close.bids, close.asks, best.option.side)) is not None:
            follower_clv = m - best.fill.effective_price
        src_close = quotes.closing_book(CaptureVenue.POLYMARKET, wager.book_key, kickoff)
        if src_close and (m := mid(src_close.bids, src_close.asks, Side.LONG)) is not None:
            trader_clv = m - wager.price
    return replace(
        head,
        verdict=Verdict.SCORED,
        best=best,
        quotes=tuple(results),
        slippage=best.fill.avg_price - wager.price,
        follower_clv=follower_clv,
        trader_clv=trader_clv,
    )


def _quote(
    opt: BuyOption,
    state: MatchState,
    diffs: tuple[str, ...],
    quotes: QuoteSource,
    settings: CopyabilitySettings,
    follow_at: datetime,
    kickoff: datetime,
) -> VenueQuote:
    looked = quotes.book_at(opt.venue, opt.book_key, follow_at, kickoff)
    if looked.book is None:
        return VenueQuote(opt, state, diffs, problem=looked.problem or "no captured book")
    if (
        looked.age_bound_seconds is not None
        and looked.age_bound_seconds > settings.max_quote_age_seconds
    ):
        stale = f"book polled only every {looked.age_bound_seconds} s at that time"
        return VenueQuote(
            opt, state, diffs, problem=stale, age_bound_seconds=looked.age_bound_seconds
        )
    try:
        fees = fee_model(opt.venue, opt.raw)
    except FeeModelError as exc:
        return VenueQuote(opt, state, diffs, problem=str(exc))
    lot = _lot(opt)
    levels = buy_levels(looked.book.bids, looked.book.asks, opt.side)
    fill = simulate_buy(
        levels, settings.stake_usd, lot=lot, fees=fees, in_play=follow_at >= kickoff
    )
    problem = None if fill else "no offers within the stake"
    return VenueQuote(
        opt, state, diffs, fill, problem, looked.book.observed_at, looked.age_bound_seconds
    )


def _cost(q: VenueQuote) -> tuple[Decimal, str]:
    assert q.fill is not None
    return q.fill.effective_price, q.option.venue.value


def _lot(opt: BuyOption) -> Decimal:
    if opt.venue is CaptureVenue.POLYMARKET_US and opt.raw.get("minimumTradeQty"):
        return Decimal(str(opt.raw["minimumTradeQty"]))
    return DEFAULT_LOTS[opt.venue]


def summarize(scores: Sequence[CopyScore]) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in scores:
        out[s.verdict.value] = out.get(s.verdict.value, 0) + 1
    return out
