from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from sharp_eyes.capture.records import BetType, CaptureVenue, Period
from sharp_eyes.domain import MatchState
from sharp_eyes.matching.nfl import OVER, UNDER, OptionIndex, Proposition, Side, classify_match
from sharp_eyes.taxonomy.settlement import (
    OvertimeRule,
    PostponementRule,
    SettlementRules,
    TieRule,
    rule_differences,
)
from sharp_eyes.taxonomy.templates import (
    TEMPLATES,
    AttachStatus,
    attach_template,
    template_for,
)
from tests.nfl_fixture import load_catalog

GAME = "NFL|2026-10-25|NFL:NO|NFL:PIT"
PM, US, KX, NV = (
    CaptureVenue.POLYMARKET,
    CaptureVenue.POLYMARKET_US,
    CaptureVenue.KALSHI,
    CaptureVenue.NOVIG,
)


@pytest.fixture(scope="module")
def catalog():  # type: ignore[no-untyped-def]
    return load_catalog()


@pytest.fixture(scope="module")
def index(catalog) -> OptionIndex:  # type: ignore[no-untyped-def]
    return OptionIndex.build(*catalog)


def test_templates_are_unique_and_complete() -> None:
    keys = [t.key for t in TEMPLATES]
    assert len(keys) == len(set(keys))
    for t in TEMPLATES:
        rules = t.rules
        # Every reviewed template states the terms that decide NFL payouts.
        assert rules.overtime is not None, t.key
        assert rules.postponement is not None and rules.cancellation is not None, t.key
        if t.bet_type is BetType.MONEYLINE:
            assert rules.tie is TieRule.SETTLES_AT_FIXED_PRICE and rules.tie_price == Decimal("0.5")
        assert t.sources, t.key


def test_every_live_listing_matches_its_reviewed_wording(catalog) -> None:  # type: ignore[no-untyped-def]
    _, markets = catalog
    for m in markets:
        attached = attach_template(m)
        assert attached.status is AttachStatus.ATTACHED, (m.venue, m.venue_market_type, attached)


def test_changed_rules_text_is_reported_as_drift(catalog) -> None:  # type: ignore[no-untyped-def]
    _, markets = catalog
    pm_ml = next(m for m in markets if m.venue is PM and m.venue_market_type == "moneyline")
    edited = replace(
        pm_ml,
        raw={**pm_ml.raw, "description": pm_ml.raw["description"].replace("50-50", "to No")},
    )
    attached = attach_template(edited)
    assert attached.status is AttachStatus.RULES_DRIFT
    assert attached.rules is None and any("50-50" in p for p in attached.problems)

    novig = next(m for m in markets if m.venue is NV)
    assert attach_template(replace(novig, raw={**novig.raw, "voids": "PUSH"})).status is (
        AttachStatus.RULES_DRIFT
    )


def test_each_listing_gets_the_reviewed_version_its_wording_matches(catalog) -> None:  # type: ignore[no-untyped-def]
    _, markets = catalog
    old = next(m for m in markets if m.venue_market_type == "football_team_full_game_winner")
    attached = attach_template(old)
    assert attached.template is not None and attached.template.version == 1
    assert attached.rules is not None and attached.rules.postponement_window_hours == 14 * 24
    two_days = (
        "If the game is delayed, postponed, suspended or otherwise rescheduled to a date and "
        "time not within two days of the originally scheduled date and time, the market will "
        "settle to the last fair market price."
    )
    description = old.raw["description"]
    start = description.index("If the game is delayed")
    end = description.index("last fair market price", start) + len("last fair market price.")
    new = replace(
        old, raw={**old.raw, "description": description[:start] + two_days + description[end:]}
    )
    attached = attach_template(new)
    assert attached.template is not None and attached.template.version == 2
    assert attached.rules is not None and attached.rules.postponement_window_hours == 48


def test_unknown_market_type_has_no_template(catalog) -> None:  # type: ignore[no-untyped-def]
    _, markets = catalog
    m = replace(markets[0], venue_market_type="anytime_touchdown")
    assert attach_template(m).status is AttachStatus.NO_TEMPLATE


def test_tie_rule_follows_the_line() -> None:
    kalshi_spread = template_for(KX, "KXNFLSPREAD")
    assert kalshi_spread is not None
    assert kalshi_spread.rules_for_line(Decimal("3.5")).tie is TieRule.IMPOSSIBLE
    assert kalshi_spread.rules_for_line(Decimal("3")).tie is TieRule.LOSES
    novig_spread = template_for(NV, "SPREAD")
    assert novig_spread is not None
    assert novig_spread.rules_for_line(Decimal("-3")).tie is None  # Unreviewed: unknown
    assert novig_spread.rules_for_line(Decimal("-3.25")).tie is None


def test_rule_differences_treat_parameters_and_unknowns_differently() -> None:
    a = SettlementRules(
        overtime=OvertimeRule.INCLUDED,
        postponement=PostponementRule.STANDS_IF_PLAYED_WITHIN_WINDOW,
        postponement_window_hours=48,
    )
    b = a.model_copy(update={"postponement": PostponementRule.STANDS_UNTIL_PLAYED,
                             "postponement_window_hours": None})  # fmt: skip
    diffs = rule_differences(a, b)
    assert "postponement" in diffs and "postponement_window_hours" in diffs
    assert "tie:unknown" in diffs  # Unknown on both sides is still not equivalence
    assert "tie_price" not in diffs  # A parameter unset on both sides is fine


def test_classify_match() -> None:
    kalshi = template_for(KX, "KXNFLGAME")
    novig = template_for(NV, "MONEY")
    pm = template_for(PM, "moneyline")
    us = template_for(US, "football_team_full_game_winner", version=1)
    us2 = template_for(US, "football_team_full_game_winner")
    assert kalshi and novig and pm and us and us2
    assert classify_match(kalshi.rules, novig.rules)[0] is MatchState.EXACT
    # Polymarket keeps a postponed game open indefinitely: a contingency-only difference.
    state, diffs = classify_match(pm.rules, kalshi.rules)
    assert state is MatchState.EQUIVALENT_WITH_RULE_DIFFERENCE and "postponement" in diffs
    assert classify_match(us.rules, kalshi.rules)[0] is (
        MatchState.EQUIVALENT_WITH_RULE_DIFFERENCE
    )  # Two-week vs 48-hour reschedule window
    assert classify_match(us2.rules, kalshi.rules)[0] is MatchState.EXACT
    regulation = kalshi.rules.model_copy(update={"overtime": OvertimeRule.EXCLUDED})
    assert classify_match(kalshi.rules, regulation)[0] is MatchState.NOT_EQUIVALENT
    unknown = kalshi.rules.model_copy(update={"overtime": None})
    assert classify_match(kalshi.rules, unknown)[0] is MatchState.AMBIGUOUS


def test_every_core_listing_resolves(index: OptionIndex) -> None:
    assert index.unresolved == []
    assert {o.venue for o in index.options} == {PM, US, KX, NV}


def _venues(index: OptionIndex, prop: Proposition) -> set[tuple[CaptureVenue, Side]]:
    return {(o.venue, o.side) for o in index.equivalents(prop)}


def test_moneyline_options_on_all_venues(index: OptionIndex) -> None:
    saints = Proposition(GAME, BetType.MONEYLINE, Period.FULL_GAME, "NFL:NO")
    assert _venues(index, saints) == {
        (PM, Side.LONG),  # Saints token
        (US, Side.SHORT),  # The market's long side is the Steelers
        (KX, Side.LONG),  # KXNFLGAME-...-NO
        (KX, Side.SHORT),  # NO on KXNFLGAME-...-PIT
        (NV, Side.LONG),
    }


def test_spread_sign_conventions(index: OptionIndex) -> None:
    pit_minus = Proposition(GAME, BetType.SPREAD, Period.FULL_GAME, "NFL:PIT", Decimal("-3.5"))
    # Polymarket "Spread: Steelers (-3.5)", Kalshi "Pittsburgh wins by over 3.5", Novig "PIT -3.5".
    assert _venues(index, pit_minus) == {(PM, Side.LONG), (KX, Side.LONG), (NV, Side.LONG)}
    no_plus = Proposition(GAME, BetType.SPREAD, Period.FULL_GAME, "NFL:NO", Decimal("3.5"))
    assert _venues(index, no_plus) == {(PM, Side.LONG), (KX, Side.SHORT), (NV, Side.LONG)}
    # Polymarket US lists the Steelers at +3.5, i.e. the opposite line.
    pit_plus = Proposition(GAME, BetType.SPREAD, Period.FULL_GAME, "NFL:PIT", Decimal("3.50"))
    assert _venues(index, pit_plus) == {(US, Side.LONG)}


def test_totals(index: OptionIndex) -> None:
    for pick in (OVER, UNDER):
        prop = Proposition(GAME, BetType.TOTAL, Period.FULL_GAME, pick, Decimal("44.5"))
        assert {v for v, _ in _venues(index, prop)} == {PM, US, KX, NV}


def test_team_outside_the_game_is_unresolved_not_guessed(catalog) -> None:  # type: ignore[no-untyped-def]
    events, markets = catalog
    novig_ml = next(m for m in markets if m.venue is NV and m.venue_market_type == "MONEY")
    books = (replace(novig_ml.books[0], outcome="ATL"), novig_ml.books[1])
    index = OptionIndex.build(events, [replace(novig_ml, books=books)])
    assert index.options == [] and len(index.unresolved) == 1
    assert "not resolved" in index.unresolved[0].reason
