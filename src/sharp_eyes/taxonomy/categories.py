"""Controlled sport and market-category taxonomy (spec section 4).

The taxonomy is versioned. Every qualification, metric and market definition
records the ``TAXONOMY_VERSION`` that produced it, so a later change to this
module never silently re-labels historical records. Bump the version whenever a
category is added, removed, renamed or re-scoped.
"""

from __future__ import annotations

from enum import StrEnum

TAXONOMY_VERSION = "2026.10.0"


class Sport(StrEnum):
    NFL = "NFL"
    NBA = "NBA"
    TENNIS = "TENNIS"


class MarketCategory(StrEnum):
    # Game markets (NFL, NBA)
    MONEYLINE = "MONEYLINE"
    SPREAD = "SPREAD"
    GAME_TOTAL = "GAME_TOTAL"
    TEAM_TOTAL = "TEAM_TOTAL"
    FIRST_HALF_MONEYLINE = "FIRST_HALF_MONEYLINE"
    FIRST_HALF_SPREAD = "FIRST_HALF_SPREAD"
    FIRST_HALF_TOTAL = "FIRST_HALF_TOTAL"
    FIRST_QUARTER_MONEYLINE = "FIRST_QUARTER_MONEYLINE"
    FIRST_QUARTER_SPREAD = "FIRST_QUARTER_SPREAD"
    FIRST_QUARTER_TOTAL = "FIRST_QUARTER_TOTAL"
    # Player props
    PLAYER_PROP_POINTS = "PLAYER_PROP_POINTS"
    PLAYER_PROP_YARDS = "PLAYER_PROP_YARDS"
    PLAYER_PROP_RECEPTIONS = "PLAYER_PROP_RECEPTIONS"
    PLAYER_PROP_REBOUNDS = "PLAYER_PROP_REBOUNDS"
    PLAYER_PROP_ASSISTS = "PLAYER_PROP_ASSISTS"
    PLAYER_PROP_COMBINATIONS = "PLAYER_PROP_COMBINATIONS"
    PLAYER_PROP_OTHER = "PLAYER_PROP_OTHER"
    # Tennis
    MATCH_WINNER = "MATCH_WINNER"
    SET_HANDICAP = "SET_HANDICAP"
    GAME_HANDICAP = "GAME_HANDICAP"
    TOTAL_GAMES = "TOTAL_GAMES"
    SET_BETTING = "SET_BETTING"
    OTHER_MATCH_MARKET = "OTHER_MATCH_MARKET"


class Period(StrEnum):
    """The portion of the event a market settles on."""

    FULL_GAME = "FULL_GAME"  # NFL/NBA game; overtime treatment lives in settlement rules
    FIRST_HALF = "FIRST_HALF"
    FIRST_QUARTER = "FIRST_QUARTER"
    MATCH = "MATCH"  # Tennis full match
    SET = "SET"  # Tennis single-set market; the set number is part of the selection


_C = MarketCategory

SPORT_CATEGORIES: dict[Sport, frozenset[MarketCategory]] = {
    Sport.NFL: frozenset(
        {
            _C.MONEYLINE,
            _C.SPREAD,
            _C.GAME_TOTAL,
            _C.TEAM_TOTAL,
            _C.FIRST_HALF_MONEYLINE,
            _C.FIRST_HALF_SPREAD,
            _C.FIRST_HALF_TOTAL,
            _C.FIRST_QUARTER_MONEYLINE,
            _C.FIRST_QUARTER_SPREAD,
            _C.FIRST_QUARTER_TOTAL,
            _C.PLAYER_PROP_POINTS,
            _C.PLAYER_PROP_YARDS,
            _C.PLAYER_PROP_RECEPTIONS,
            _C.PLAYER_PROP_OTHER,
        }
    ),
    Sport.NBA: frozenset(
        {
            _C.MONEYLINE,
            _C.SPREAD,
            _C.GAME_TOTAL,
            _C.TEAM_TOTAL,
            _C.FIRST_HALF_MONEYLINE,
            _C.FIRST_HALF_SPREAD,
            _C.FIRST_HALF_TOTAL,
            _C.FIRST_QUARTER_MONEYLINE,
            _C.FIRST_QUARTER_SPREAD,
            _C.FIRST_QUARTER_TOTAL,
            _C.PLAYER_PROP_POINTS,
            _C.PLAYER_PROP_REBOUNDS,
            _C.PLAYER_PROP_ASSISTS,
            _C.PLAYER_PROP_COMBINATIONS,
            _C.PLAYER_PROP_OTHER,
        }
    ),
    Sport.TENNIS: frozenset(
        {
            _C.MATCH_WINNER,
            _C.SET_HANDICAP,
            _C.GAME_HANDICAP,
            _C.TOTAL_GAMES,
            _C.SET_BETTING,
            _C.OTHER_MATCH_MARKET,
        }
    ),
}

# Categories whose identity requires a numeric handicap or total line.
LINE_REQUIRED: frozenset[MarketCategory] = frozenset(
    {
        _C.SPREAD,
        _C.GAME_TOTAL,
        _C.TEAM_TOTAL,
        _C.FIRST_HALF_SPREAD,
        _C.FIRST_HALF_TOTAL,
        _C.FIRST_QUARTER_SPREAD,
        _C.FIRST_QUARTER_TOTAL,
        _C.PLAYER_PROP_POINTS,
        _C.PLAYER_PROP_YARDS,
        _C.PLAYER_PROP_RECEPTIONS,
        _C.PLAYER_PROP_REBOUNDS,
        _C.PLAYER_PROP_ASSISTS,
        _C.PLAYER_PROP_COMBINATIONS,
        _C.SET_HANDICAP,
        _C.GAME_HANDICAP,
        _C.TOTAL_GAMES,
    }
)

# Categories that must not carry a line (a moneyline with a line is a spread).
LINE_FORBIDDEN: frozenset[MarketCategory] = frozenset(
    {
        _C.MONEYLINE,
        _C.FIRST_HALF_MONEYLINE,
        _C.FIRST_QUARTER_MONEYLINE,
        _C.MATCH_WINNER,
        _C.SET_BETTING,
    }
)

PLAYER_PROP_CATEGORIES: frozenset[MarketCategory] = frozenset(
    c for c in MarketCategory if c.value.startswith("PLAYER_PROP_")
)

# Totals settle on Over/Under rather than on a participant.
TOTAL_CATEGORIES: frozenset[MarketCategory] = frozenset(
    {
        _C.GAME_TOTAL,
        _C.TEAM_TOTAL,
        _C.FIRST_HALF_TOTAL,
        _C.FIRST_QUARTER_TOTAL,
        _C.TOTAL_GAMES,
    }
)

_CATEGORY_PERIOD: dict[MarketCategory, Period] = {
    _C.FIRST_HALF_MONEYLINE: Period.FIRST_HALF,
    _C.FIRST_HALF_SPREAD: Period.FIRST_HALF,
    _C.FIRST_HALF_TOTAL: Period.FIRST_HALF,
    _C.FIRST_QUARTER_MONEYLINE: Period.FIRST_QUARTER,
    _C.FIRST_QUARTER_SPREAD: Period.FIRST_QUARTER,
    _C.FIRST_QUARTER_TOTAL: Period.FIRST_QUARTER,
}


class TaxonomyError(ValueError):
    """A sport/category/period combination outside the controlled taxonomy."""


def categories_for(sport: Sport) -> frozenset[MarketCategory]:
    return SPORT_CATEGORIES[sport]


def validate_category(sport: Sport, category: MarketCategory) -> None:
    if category not in SPORT_CATEGORIES[sport]:
        raise TaxonomyError(f"{category} is not a {sport} market category")


def default_period(sport: Sport, category: MarketCategory) -> Period:
    """The period implied by a category. Tennis set markets must state SET explicitly."""
    validate_category(sport, category)
    if category in _CATEGORY_PERIOD:
        return _CATEGORY_PERIOD[category]
    return Period.MATCH if sport is Sport.TENNIS else Period.FULL_GAME


def allowed_periods(sport: Sport, category: MarketCategory) -> frozenset[Period]:
    validate_category(sport, category)
    if sport is Sport.TENNIS:
        if category in {_C.MATCH_WINNER, _C.SET_BETTING, _C.SET_HANDICAP}:
            return frozenset({Period.MATCH})
        # Game handicaps, total games and other markets may be match- or set-scoped.
        return frozenset({Period.MATCH, Period.SET})
    return frozenset({default_period(sport, category)})
