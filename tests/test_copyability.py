from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from sharp_eyes.capture.records import CaptureVenue, Level
from sharp_eyes.copyability.fill import buy_levels, mid, simulate_buy
from sharp_eyes.copyability.score import (
    BookLookup,
    BookView,
    CopyabilitySettings,
    Timing,
    Verdict,
    score_wager,
)
from sharp_eyes.copyability.wagers import SourceFill, Wager, aggregate_wagers
from sharp_eyes.domain import MatchState
from sharp_eyes.matching.nfl import OptionIndex, Side
from sharp_eyes.pricing.fees import FeeModel
from tests.nfl_fixture import load_catalog

PM, US, KX, NV = (
    CaptureVenue.POLYMARKET,
    CaptureVenue.POLYMARKET_US,
    CaptureVenue.KALSHI,
    CaptureVenue.NOVIG,
)
KICKOFF = datetime(2026, 10, 25, 13, 30, tzinfo=UTC)
SAINTS_PM = "16013029087006534797924862977185419395437649810045162973335886530817974510015"
SAINTS_KX = "KXNFLGAME-26OCT25PITNO-NO"
STEELERS_KX = "KXNFLGAME-26OCT25PITNO-PIT"
SAINTS_NV = "01a136e2-e79c-70a2-8a3f-bd712d50f70e"
US_GAME = "aec-nfl-pit-no-2026-10-25"
NO_FEE = FeeModel(KX, D(0))


def _fill(minute: float, side: str = "BUY", price: str = "0.40", size: str = "100", **kw):  # type: ignore[no-untyped-def]
    ts = KICKOFF - timedelta(hours=2) + timedelta(minutes=minute)
    base = {
        "wallet": "0xabc",
        "market_id": "m1",
        "book_key": SAINTS_PM,
        "side": side,
        "price": D(price),
        "size": D(size),
        "ts": ts,
        "observed_at": ts + timedelta(seconds=20),
    }
    return SourceFill(**{**base, **kw})


# -- wagers ------------------------------------------------------------------


def test_fills_aggregate_into_wagers() -> None:
    fills = [
        _fill(0, price="0.40", size="100", taker=True),
        _fill(0.5, price="0.42", size="300", taker=False),
        _fill(5),  # More than 60 s later: a new wager
        _fill(5.2, side="SELL"),  # A sell ends the run and is not a wager
        _fill(5.4),
        _fill(5.5, wallet="0xdef"),  # Another wallet is its own wager
    ]
    wagers = aggregate_wagers(fills, window_seconds=60)
    assert [(w.wallet, w.fills) for w in wagers] == [
        ("0xabc", 2),
        ("0xabc", 1),
        ("0xabc", 1),
        ("0xdef", 1),
    ]
    first = wagers[0]
    assert first.price == D("0.415") and first.size == 400
    assert first.notional == D("166.000")
    assert first.taker_share == D("0.25")
    assert first.detected_at == fills[0].observed_at


# -- fills -------------------------------------------------------------------


def test_short_side_buys_from_bids() -> None:
    bids: list[Level] = [(D("0.60"), D("5")), (D("0.58"), D("10"))]
    asks: list[Level] = [(D("0.63"), D("5"))]
    assert buy_levels(bids, asks, Side.SHORT) == [(D("0.40"), D("5")), (D("0.42"), D("10"))]
    assert mid(bids, asks, Side.LONG) == D("0.615")
    assert mid(bids, asks, Side.SHORT) == D("0.385")
    assert mid([], asks, Side.LONG) is None


def test_simulate_buy_walks_depth_in_whole_lots() -> None:
    levels: list[Level] = [(D("0.40"), D("10")), (D("0.45"), D("100"))]
    fill = simulate_buy(levels, D("10"), lot=D("1"), fees=NO_FEE, in_play=False)
    assert fill is not None
    # 10 at 0.40 = 4.00, then 13 at 0.45 = 5.85 (a 14th would exceed $10).
    assert (fill.qty, fill.cost, fill.levels, fill.complete) == (D(23), D("9.85"), 2, True)
    assert fill.best_price == D("0.40")

    thin = simulate_buy([(D("0.40"), D("5"))], D("10"), lot=D("1"), fees=NO_FEE, in_play=False)
    assert thin is not None and not thin.complete and thin.qty == 5

    assert (
        simulate_buy([(D("0.40"), D("5"))], D("0.30"), lot=D(1), fees=NO_FEE, in_play=False) is None
    )
    assert simulate_buy([], D("10"), lot=D("1"), fees=NO_FEE, in_play=False) is None


def test_fees_raise_the_effective_price() -> None:
    kalshi = FeeModel(KX, D("0.07"), quantum=D("0.0001"), rounding="ROUND_CEILING")
    fill = simulate_buy([(D("0.50"), D("100"))], D("10"), lot=D("1"), fees=kalshi, in_play=False)
    assert fill is not None
    assert fill.fee == D("0.35") and fill.effective_price == D("0.5175")


# -- scoring -----------------------------------------------------------------


@dataclass
class FakeQuotes:
    books: dict[tuple[CaptureVenue, str], BookView] = field(default_factory=dict)
    closing: dict[tuple[CaptureVenue, str], BookView] = field(default_factory=dict)
    age_bound: int = 15

    def book_at(self, venue, book_key, at, kickoff):  # type: ignore[no-untyped-def]
        book = self.books.get((venue, book_key))
        return BookLookup(book, None if book else "no book", self.age_bound)

    def closing_book(self, venue, book_key, kickoff):  # type: ignore[no-untyped-def]
        return self.closing.get((venue, book_key))


def _book(bid: str, ask: str, size: str = "1000") -> BookView:
    return BookView(((D(bid), D(size)),), ((D(ask), D(size)),), KICKOFF - timedelta(hours=3))


@pytest.fixture(scope="module")
def index() -> OptionIndex:
    return OptionIndex.build(*load_catalog())


def _wager(hours_before: float = 2, book_key: str = SAINTS_PM) -> Wager:
    ts = KICKOFF - timedelta(hours=hours_before)
    return Wager(
        "0xabc", "m1", book_key, D("0.40"), D("500"), ts, ts, ts + timedelta(seconds=30), 1, None
    )


def test_follower_takes_the_cheapest_fee_inclusive_offer(index: OptionIndex) -> None:
    quotes = FakeQuotes(
        books={
            (KX, SAINTS_KX): _book("0.40", "0.42"),  # 0.42 + Kalshi fee ~0.017
            (KX, STEELERS_KX): _book("0.57", "0.59"),  # Saints via NO at 1 - 0.57 = 0.43
            (NV, SAINTS_NV): _book("0.41", "0.43"),  # No fee before kickoff
            (US, US_GAME): _book("0.56", "0.58"),  # Saints via short at 0.44
        },
        closing={(NV, SAINTS_NV): _book("0.45", "0.47"), (PM, SAINTS_PM): _book("0.45", "0.46")},
    )
    score = score_wager(_wager(), index, quotes, CopyabilitySettings(), now=KICKOFF)
    assert score.verdict is Verdict.SCORED and score.timing is Timing.PRE_GAME
    assert score.best is not None and score.best.option.venue is NV
    assert len(score.quotes) == 4
    assert score.slippage == D("0.03")
    assert score.follower_clv == D("0.03")  # Closing mid 0.46 minus 0.43
    assert score.trader_clv == D("0.055")  # Polymarket closing mid 0.455 minus 0.40
    assert score.detection_seconds == 30
    assert score.best.state is MatchState.EQUIVALENT_WITH_RULE_DIFFERENCE

    # Only the Steelers NO is quoted: Saints bought as the short side of that market.
    short_only = FakeQuotes(books={(KX, STEELERS_KX): _book("0.57", "0.59")})
    score = score_wager(_wager(), index, short_only, CopyabilitySettings(), now=KICKOFF)
    assert score.best is not None and score.best.option.side is Side.SHORT
    assert score.best.fill is not None and score.best.fill.avg_price == D("0.43")
    assert score.follower_clv is None  # No closing book captured


def test_missing_or_stale_books_are_unscorable_not_guessed(index: OptionIndex) -> None:
    score = score_wager(_wager(), index, FakeQuotes(), CopyabilitySettings())
    assert score.verdict is Verdict.UNSCORABLE and score.reason == "no book"

    stale = FakeQuotes(books={(NV, SAINTS_NV): _book("0.41", "0.43")}, age_bound=900)
    score = score_wager(_wager(), index, stale, CopyabilitySettings(max_quote_age_seconds=600))
    assert score.verdict is Verdict.UNSCORABLE and "900 s" in (score.reason or "")

    thin = FakeQuotes(books={(NV, SAINTS_NV): _book("0.41", "0.43", size="2")})
    score = score_wager(_wager(), index, thin, CopyabilitySettings())
    assert score.verdict is Verdict.UNSCORABLE and "too thin" in (score.reason or "")
    partial = CopyabilitySettings(require_complete_fill=False)
    assert score_wager(_wager(), index, thin, partial).verdict is Verdict.SCORED


def test_scope_verdicts(index: OptionIndex) -> None:
    quotes = FakeQuotes(books={(NV, SAINTS_NV): _book("0.41", "0.43")})
    in_play = score_wager(_wager(hours_before=-0.5), index, quotes, CopyabilitySettings())
    assert in_play.verdict is Verdict.IN_PLAY

    late = score_wager(_wager(hours_before=30 / 3600), index, quotes, CopyabilitySettings())
    assert late.verdict is Verdict.UNSCORABLE and late.reason == "detected after kickoff"

    unmapped = score_wager(_wager(book_key="123"), index, quotes, CopyabilitySettings())
    assert unmapped.verdict is Verdict.NOT_MAPPED

    exact_only = CopyabilitySettings(accept_states=(MatchState.EXACT,))
    no_match = score_wager(_wager(), index, quotes, exact_only)
    assert no_match.verdict is Verdict.NO_MATCH
    assert no_match.reason == "only EQUIVALENT_WITH_RULE_DIFFERENCE matches"

    kalshi_only = CopyabilitySettings(target_venues=(KX,))
    assert score_wager(_wager(), index, quotes, kalshi_only).reason == "no book"
