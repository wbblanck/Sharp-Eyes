"""Canonical market identity (spec 4.2).

A ``MarketIdentity`` names exactly one bet: Team A moneyline, Team A -3.5,
game total over 44.5 and first-half total over 21.5 are four different
identities even though they share an event. The identity key is a stable hash
of every term that changes what the contract pays, so two listings collapse to
the same canonical market only when they agree on all of them.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from sharp_eyes.taxonomy.categories import (
    LINE_FORBIDDEN,
    LINE_REQUIRED,
    PLAYER_PROP_CATEGORIES,
    TAXONOMY_VERSION,
    TOTAL_CATEGORIES,
    MarketCategory,
    Period,
    Sport,
    TaxonomyError,
    allowed_periods,
    validate_category,
)
from sharp_eyes.taxonomy.settlement import SettlementRules

# Selections for totals; every other category selects a participant id.
OVER = "OVER"
UNDER = "UNDER"
# Handicap and total lines are quoted in half points (or whole points).
_LINE_STEP = Decimal("0.5")


class MarketIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sport: Sport
    event_key: str
    category: MarketCategory
    period: Period
    # A canonical participant key for side markets, or OVER/UNDER for totals.
    selection: str
    line: Decimal | None = None
    # For team totals the team, for player props the player (canonical keys).
    subject: str | None = None
    set_number: int | None = None  # Tennis SET-period markets only
    prop_stat: str | None = None  # PLAYER_PROP_OTHER / COMBINATIONS, e.g. "PTS+REB+AST"
    match_format: str | None = None  # Tennis "BO3"/"BO5"; None for team sports
    settlement_rules: SettlementRules
    taxonomy_version: str = TAXONOMY_VERSION

    @model_validator(mode="after")
    def _check(self) -> MarketIdentity:
        validate_category(self.sport, self.category)
        if self.period not in allowed_periods(self.sport, self.category):
            raise TaxonomyError(f"{self.category} cannot settle on period {self.period}")
        if (self.period is Period.SET) != (self.set_number is not None):
            raise TaxonomyError("set_number is required exactly when period is SET")

        if self.category in LINE_REQUIRED and self.line is None:
            raise TaxonomyError(f"{self.category} requires a line")
        if self.category in LINE_FORBIDDEN and self.line is not None:
            raise TaxonomyError(f"{self.category} must not carry a line")
        if self.line is not None and (self.line % _LINE_STEP) != 0:
            raise TaxonomyError(f"line {self.line} is not on a half-point grid")
        if self.category in TOTAL_CATEGORIES and self.line is not None and self.line < 0:
            raise TaxonomyError("a total cannot be negative")

        over_under = self.category in TOTAL_CATEGORIES or self.category in PLAYER_PROP_CATEGORIES
        if over_under and self.selection not in {OVER, UNDER}:
            raise TaxonomyError(f"{self.category} selection must be OVER or UNDER")
        if not over_under and self.selection in {OVER, UNDER}:
            raise TaxonomyError(f"{self.category} selects a participant, not OVER/UNDER")

        needs_subject = (
            self.category in PLAYER_PROP_CATEGORIES or self.category is MarketCategory.TEAM_TOTAL
        )
        if needs_subject != (self.subject is not None):
            raise TaxonomyError(
                f"{self.category} subject must be set exactly for props/team totals"
            )
        needs_stat = self.category in {
            MarketCategory.PLAYER_PROP_OTHER,
            MarketCategory.PLAYER_PROP_COMBINATIONS,
        }
        if needs_stat != (self.prop_stat is not None):
            raise TaxonomyError(f"{self.category} prop_stat must be set exactly for other/combos")
        if (self.sport is Sport.TENNIS) != (self.match_format is not None):
            raise TaxonomyError("match_format is required for tennis and only for tennis")
        return self

    def _key_fields(self) -> dict[str, object]:
        return {
            "sport": self.sport.value,
            "event_key": self.event_key,
            "category": self.category.value,
            "period": self.period.value,
            "selection": self.selection,
            # Normalise so -3.5 and -3.50 hash identically.
            "line": None if self.line is None else str(self.line.normalize()),
            "subject": self.subject,
            "set_number": self.set_number,
            "prop_stat": self.prop_stat,
            "match_format": self.match_format,
            "settlement_rules": self.settlement_rules.rules_hash(),
            "taxonomy_version": self.taxonomy_version,
        }

    def identity_key(self) -> str:
        payload = json.dumps(self._key_fields(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()
