"""Hand-reviewed settlement templates per venue market type (audit recommendation 7).

A venue lists hundreds of NFL markets a week, but only a handful of market
*types*, and every listing of a type settles under the same contract terms.
So the terms are read once per type from the venue's own rules, written down
here as a versioned :class:`SettlementTemplate`, and attached to every listing
of that type. Free-text parsing per listing is never used to decide payouts.

Each template also carries ``checks``: phrases the listing's own rules text
must contain. Venues change their rules without notice; when a listing no
longer contains the reviewed wording, :func:`attach_template` reports
``RULES_DRIFT`` instead of silently applying stale terms, and the type needs a
fresh review (and a version bump).

Review record: every template below was checked on 2026-10-24 against the
source named in ``sources`` (live listings for Polymarket and Polymarket US,
which publish their rules per market; contract terms filed with the CFTC for
Kalshi and Novig, which publish rules per product). Unknown terms stay
``None`` and make a match AMBIGUOUS rather than EXACT.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sharp_eyes.capture.records import BetType, CaptureVenue, MarketRecord, Period
from sharp_eyes.taxonomy.settlement import (
    CancellationRule,
    InactivePlayerRule,
    OvertimeRule,
    PostponementRule,
    RetirementRule,
    SettlementRules,
    TieRule,
)

TEMPLATE_SET_VERSION = "2026.10.24"

_HALF = Decimal("0.5")


class OutcomeShape(StrEnum):
    # Each outcome has its own book (Polymarket tokens, Novig outcomes).
    TWO_WAY = "TWO_WAY"
    # One YES/NO contract per proposition; the other side is bought as NO
    # (Kalshi markets, Polymarket US long/short sides).
    YES_NO = "YES_NO"


class AttachStatus(StrEnum):
    ATTACHED = "ATTACHED"
    NO_TEMPLATE = "NO_TEMPLATE"  # Market type not reviewed yet
    RULES_DRIFT = "RULES_DRIFT"  # Listing text no longer matches the reviewed wording


@dataclass(frozen=True)
class RulesCheck:
    """``field`` of the listing's raw payload must contain every phrase in ``contains``."""

    field: str
    contains: tuple[str, ...]


@dataclass(frozen=True)
class SettlementTemplate:
    venue: CaptureVenue
    venue_market_type: str
    version: int
    bet_type: BetType
    period: Period
    shape: OutcomeShape
    rules: SettlementRules
    # Rule when a spread or total lands exactly on a whole-number line. Half-point
    # lines cannot tie, which :meth:`rules_for_line` applies automatically.
    whole_line_tie: TieRule | None = None
    checks: tuple[RulesCheck, ...] = ()
    sources: tuple[str, ...] = ()
    reviewed_on: date = date(2026, 10, 24)
    notes: str = ""

    @property
    def key(self) -> str:
        return f"{self.venue.value}:{self.venue_market_type}@v{self.version}"

    def rules_for_line(self, line: Decimal | None) -> SettlementRules:
        """The concrete rules for one listing. Moneylines keep the template's tie rule."""
        if self.bet_type in (BetType.SPREAD, BetType.TOTAL, BetType.TEAM_TOTAL):
            if line is None:
                return self.rules.model_copy(update={"tie": None, "tie_price": None})
            whole = line % 1 == 0
            tie = self.whole_line_tie if whole else TieRule.IMPOSSIBLE
            if not whole and line % _HALF != 0:
                tie = None  # Quarter lines and the like: not reviewed
            return self.rules.model_copy(update={"tie": tie, "tie_price": None})
        return self.rules

    def drift(self, raw: Mapping[str, Any]) -> list[str]:
        """Reviewed phrases missing from the listing's rules text."""
        missing = []
        for check in self.checks:
            text = str(raw.get(check.field) or "")
            missing += [f"{check.field}: {p!r}" for p in check.contains if p not in text]
        return missing


@dataclass(frozen=True)
class TemplateAttachment:
    status: AttachStatus
    template: SettlementTemplate | None = None
    rules: SettlementRules | None = None
    problems: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Shared terms
# ---------------------------------------------------------------------------

_NFL = {
    "retirement": RetirementRule.NOT_APPLICABLE,
    "inactive_player": InactivePlayerRule.NOT_APPLICABLE,
    "payout_per_contract_usd": Decimal("1"),
    "settlement_source": "official league result",
}

# Polymarket (international). Rules are the market ``description``.
_PM_POSTPONED = (
    "If the game is postponed, this market will remain open until the game has been completed."
)
_PM_CANCELED = (
    "If the game is canceled entirely, with no make-up game, this market will resolve 50-50."
)
_PM = SettlementRules(
    **_NFL,
    overtime=OvertimeRule.INCLUDED,
    postponement=PostponementRule.STANDS_UNTIL_PLAYED,
    cancellation=CancellationRule.FIXED_PRICE,
    cancellation_price=Decimal("0.5"),
)
_PM_SRC = ("Gamma market description, NFL series 12185, read 2026-10-24",)

# Polymarket US. Rules are the market ``description``; moneylines allow a two-week
# reschedule, spreads and totals two days.
_PMUS_TWO_DAYS = (
    "not within two days of the originally scheduled date and time, "
    "the market will settle to the last fair market price"
)
_PMUS = SettlementRules(
    **_NFL,
    overtime=OvertimeRule.INCLUDED,
    postponement=PostponementRule.STANDS_IF_PLAYED_WITHIN_WINDOW,
    postponement_window_hours=48,
    cancellation=CancellationRule.VENUE_FAIR_VALUE,
)
_PMUS_SRC = ("gateway.polymarket.us /v1/events market description, read 2026-10-24",)

# Kalshi: per-product contract terms; listings only carry ``rules_primary``.
_KALSHI = SettlementRules(
    **_NFL,
    overtime=OvertimeRule.INCLUDED,
    postponement=PostponementRule.STANDS_IF_PLAYED_WITHIN_WINDOW,
    postponement_window_hours=48,
    cancellation=CancellationRule.VENUE_FAIR_VALUE,
)

# Novig (Ludlow Exchange): per-series contract terms filed with the CFTC. Every
# void settles at fair value; listings carry ``voids: "FMV"``.
_NOVIG = SettlementRules(
    **_NFL,
    overtime=OvertimeRule.INCLUDED,
    postponement=PostponementRule.STANDS_IF_PLAYED_WITHIN_WINDOW,
    postponement_window_hours=48,
    cancellation=CancellationRule.VENUE_FAIR_VALUE,
)
_NOVIG_CHECK = RulesCheck("voids", ("FMV",))

_P, _B = Period, BetType
_PMV, _USV, _KXV, _NVV = (
    CaptureVenue.POLYMARKET,
    CaptureVenue.POLYMARKET_US,
    CaptureVenue.KALSHI,
    CaptureVenue.NOVIG,
)
_TIE_HALF = {"tie": TieRule.SETTLES_AT_FIXED_PRICE, "tie_price": Decimal("0.5")}

TEMPLATES: tuple[SettlementTemplate, ...] = (
    # --- Polymarket (signal source; also the reference price) ---------------
    SettlementTemplate(
        _PMV, "moneyline", 1, _B.MONEYLINE, _P.FULL_GAME, OutcomeShape.TWO_WAY,
        _PM.model_copy(update=_TIE_HALF),
        checks=(RulesCheck("description", (
            "Overtime is included if played.",
            "If the game ends in a tie, this market will resolve 50-50.",
            _PM_POSTPONED, _PM_CANCELED,
        )),),
        sources=_PM_SRC,
    ),
    SettlementTemplate(
        _PMV, "spreads", 1, _B.SPREAD, _P.FULL_GAME, OutcomeShape.TWO_WAY, _PM,
        checks=(RulesCheck("description", (
            "Overtime is included if played.", _PM_POSTPONED, _PM_CANCELED,
        )),),
        sources=_PM_SRC,
        notes="Listed on half-point lines only; whole-line behaviour unreviewed.",
    ),
    SettlementTemplate(
        _PMV, "totals", 1, _B.TOTAL, _P.FULL_GAME, OutcomeShape.TWO_WAY, _PM,
        checks=(RulesCheck("description", ("combine to score", _PM_POSTPONED, _PM_CANCELED)),),
        sources=_PM_SRC,
        notes=(
            "The text says 'in this game' without naming overtime; resolution source is the "
            "nfl.com final score, which includes overtime, so overtime is INCLUDED."
        ),
    ),
    SettlementTemplate(
        _PMV, "team_totals", 1, _B.TEAM_TOTAL, _P.FULL_GAME, OutcomeShape.TWO_WAY, _PM,
        checks=(RulesCheck("description", (
            "based solely on the", _PM_POSTPONED, _PM_CANCELED,
        )),),
        sources=_PM_SRC,
        notes="Overtime INCLUDED on the same reasoning as totals.",
    ),
    SettlementTemplate(
        _PMV, "first_half_moneyline", 1, _B.MONEYLINE, _P.FIRST_HALF, OutcomeShape.TWO_WAY,
        _PM.model_copy(update={**_TIE_HALF, "overtime": OvertimeRule.NOT_APPLICABLE}),
        checks=(RulesCheck("description", (
            "overtime is not included",
            "If both teams score the same number of points in the first half, "
            "this market will resolve 50-50.",
            _PM_POSTPONED, _PM_CANCELED,
        )),),
        sources=_PM_SRC,
    ),
    # --- Polymarket US ------------------------------------------------------
    SettlementTemplate(
        _USV, "football_team_full_game_winner", 1, _B.MONEYLINE, _P.FULL_GAME,
        OutcomeShape.YES_NO,
        _PMUS.model_copy(update={**_TIE_HALF, "postponement_window_hours": 14 * 24}),
        checks=(RulesCheck("description", (
            "Overtime is included if played.",
            "If the game ends in a tie, the market will settle to $0.50.",
            "not rescheduled to a date within two weeks of the originally scheduled date, "
            "the market will settle to the last fair market price",
        )),),
        sources=_PMUS_SRC,
        notes="Listings from before late October 2026.",
    ),
    SettlementTemplate(
        _USV, "football_team_full_game_winner", 2, _B.MONEYLINE, _P.FULL_GAME,
        OutcomeShape.YES_NO, _PMUS.model_copy(update=_TIE_HALF),
        checks=(RulesCheck("description", (
            "Overtime is included if played.",
            "If the game ends in a tie, the market will settle to $0.50.",
            _PMUS_TWO_DAYS,
        )),),
        sources=("gateway.polymarket.us market aec-nfl-car-gb-2026-10-29, read 2026-10-24",),
        notes="Newer listings use the same two-day reschedule window as spreads and totals.",
    ),
    SettlementTemplate(
        _USV, "football_team_full_game_spread", 1, _B.SPREAD, _P.FULL_GAME,
        OutcomeShape.YES_NO, _PMUS,
        checks=(RulesCheck("description", (
            "Overtime is included if played.", "point spread", _PMUS_TWO_DAYS,
        )),),
        sources=_PMUS_SRC,
        notes="Long side is the team named in marketSides[long].team at the signed line.",
    ),
    SettlementTemplate(
        _USV, "football_team_full_game_total", 1, _B.TOTAL, _P.FULL_GAME,
        OutcomeShape.YES_NO, _PMUS,
        checks=(RulesCheck("description", (
            "Overtime is included if played.", "combine for over", _PMUS_TWO_DAYS,
        )),),
        sources=_PMUS_SRC,
        notes="Long side is Over.",
    ),
    SettlementTemplate(
        _USV, "football_team_points_full_game_total", 1, _B.TEAM_TOTAL, _P.FULL_GAME,
        OutcomeShape.YES_NO, _PMUS,
        checks=(RulesCheck("description", (
            "Overtime is included if played.", "scores over", _PMUS_TWO_DAYS,
        )),),
        sources=_PMUS_SRC,
    ),
    # --- Kalshi -------------------------------------------------------------
    SettlementTemplate(
        _KXV, "KXNFLGAME", 1, _B.MONEYLINE, _P.FULL_GAME, OutcomeShape.YES_NO,
        _KALSHI.model_copy(update=_TIE_HALF),
        checks=(RulesCheck("rules_primary", ("wins the", "originally scheduled for")),),
        sources=("https://assets.kalshi.com/contract_terms/FOOTBALLGAMEWIN.pdf",),
        notes=(
            "One market per team. A tie pays $0.50 to YES and NO unless a 'Tie' strike is "
            "listed; NFL games list none (checked 2026-10-24). Abandonment before 55 minutes "
            "of play settles at the last fair price."
        ),
    ),
    SettlementTemplate(
        _KXV, "KXNFLSPREAD", 1, _B.SPREAD, _P.FULL_GAME, OutcomeShape.YES_NO, _KALSHI,
        whole_line_tie=TieRule.LOSES,
        checks=(RulesCheck("rules_primary", ("wins by more than", "originally scheduled for")),),
        sources=("https://assets.kalshi.com/contract_terms/FOOTBALLSPREAD.pdf",),
        notes="'Team wins by more than X': YES is the team at -X, NO the opponent at +X.",
    ),
    SettlementTemplate(
        _KXV, "KXNFLTOTAL", 1, _B.TOTAL, _P.FULL_GAME, OutcomeShape.YES_NO, _KALSHI,
        whole_line_tie=TieRule.LOSES,
        checks=(RulesCheck("rules_primary", ("collectively score more than",
                                             "originally scheduled for")),),
        sources=("https://assets.kalshi.com/contract_terms/FOOTBALLTOTALS.pdf",),
        notes="YES is Over X, NO is Under X.",
    ),
    # --- Novig --------------------------------------------------------------
    SettlementTemplate(
        _NVV, "MONEY", 1, _B.MONEYLINE, _P.FULL_GAME, OutcomeShape.TWO_WAY,
        _NOVIG.model_copy(update=_TIE_HALF),
        checks=(_NOVIG_CHECK,),
        sources=("Novig NFL Winner Series (NFL-004), support.novig.com/en/articles/16083642",),
        notes="A tie is a determined outcome paying $0.50 to each side, not a void.",
    ),
    SettlementTemplate(
        _NVV, "SPREAD", 1, _B.SPREAD, _P.FULL_GAME, OutcomeShape.TWO_WAY, _NOVIG,
        checks=(_NOVIG_CHECK,),
        sources=("Novig NFL Spread Series, support.novig.com/en/articles/16083642",),
        notes="Whole-line pushes not confirmed in the filed terms; whole_line_tie unknown.",
    ),
    SettlementTemplate(
        _NVV, "TOTAL", 1, _B.TOTAL, _P.FULL_GAME, OutcomeShape.TWO_WAY, _NOVIG,
        checks=(_NOVIG_CHECK,),
        sources=("Novig NFL Total Series, support.novig.com/en/articles/16083642",),
    ),
)  # fmt: skip

_BY_TYPE: dict[tuple[CaptureVenue, str], tuple[SettlementTemplate, ...]] = {}
for _t in sorted(TEMPLATES, key=lambda t: -t.version):
    _BY_TYPE[(_t.venue, _t.venue_market_type)] = (
        *_BY_TYPE.get((_t.venue, _t.venue_market_type), ()),
        _t,
    )


def template_versions(
    venue: CaptureVenue, venue_market_type: str
) -> tuple[SettlementTemplate, ...]:
    """Every reviewed version of a market type, newest first."""
    return _BY_TYPE.get((venue, venue_market_type), ())


def template_for(
    venue: CaptureVenue, venue_market_type: str, version: int | None = None
) -> SettlementTemplate | None:
    """The newest reviewed version of a market type, or a given version."""
    versions = template_versions(venue, venue_market_type)
    if version is None:
        return versions[0] if versions else None
    return next((t for t in versions if t.version == version), None)


def attach_template(market: MarketRecord) -> TemplateAttachment:
    """The reviewed rules for one listing, or why there are none.

    A venue can list the same market type under different wording at once (old
    listings keep their terms when new ones change), so each reviewed version
    is tried, newest first, and the first whose wording the listing contains
    applies. Drift is reported against the newest version.
    """
    versions = template_versions(market.venue, market.venue_market_type)
    if not versions:
        return TemplateAttachment(AttachStatus.NO_TEMPLATE)
    latest = versions[0]
    if (latest.bet_type, latest.period) != (market.bet_type, market.period):
        problem = f"capture classified {market.bet_type}/{market.period}"
        return TemplateAttachment(AttachStatus.RULES_DRIFT, latest, problems=(problem,))
    for template in versions:
        if not template.drift(market.raw):
            return TemplateAttachment(
                AttachStatus.ATTACHED, template, template.rules_for_line(market.line)
            )
    return TemplateAttachment(
        AttachStatus.RULES_DRIFT, latest, problems=tuple(latest.drift(market.raw))
    )
