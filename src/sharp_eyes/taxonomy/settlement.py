"""Settlement-rule representation (spec 4.2, 7.1).

Two contracts that agree on event, selection, line and period can still be
different bets if they settle differently: overtime, ties, postponement,
retirement and inactive-player rules all change the payout. ``SettlementRules``
captures those terms explicitly; :func:`rule_differences` lists every term on
which two rule sets disagree or cannot be compared, which the contract matcher
(SC-011) uses to decide between EXACT, EQUIVALENT_WITH_RULE_DIFFERENCE and
AMBIGUOUS.

``None`` always means *unknown*, never a default. Unknown terms are reported
as differences because equivalence cannot be shown.

Rules are attached to listings through hand-reviewed templates
(:mod:`sharp_eyes.taxonomy.templates`), not parsed from each listing's text.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class OvertimeRule(StrEnum):
    INCLUDED = "INCLUDED"  # Overtime/extra periods count toward the result
    EXCLUDED = "EXCLUDED"  # Regulation only
    NOT_APPLICABLE = "NOT_APPLICABLE"  # Period markets that end before overtime, tennis


class TieRule(StrEnum):
    """What happens when the market lands exactly on the line, or a game ends tied."""

    PUSH_REFUND = "PUSH_REFUND"  # Stake returned
    LOSES = "LOSES"  # A strict "more than" contract: YES loses, NO wins
    IMPOSSIBLE = "IMPOSSIBLE"  # Half-point line or format with no ties
    SETTLES_AT_FIXED_PRICE = "SETTLES_AT_FIXED_PRICE"  # Both sides paid ``tie_price``
    VENUE_FAIR_VALUE = "VENUE_FAIR_VALUE"  # Voided at a venue-determined fair price


class RetirementRule(StrEnum):
    """Tennis retirement / walkover / abandonment handling."""

    VOID = "VOID"
    ADVANCING_PLAYER_WINS = "ADVANCING_PLAYER_WINS"
    VOID_UNLESS_ONE_SET_COMPLETED = "VOID_UNLESS_ONE_SET_COMPLETED"
    VOID_UNLESS_MARKET_DETERMINED = "VOID_UNLESS_MARKET_DETERMINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class InactivePlayerRule(StrEnum):
    """Player props when the player does not play."""

    VOID = "VOID"
    LOSES = "LOSES"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PostponementRule(StrEnum):
    VOID = "VOID"
    # The contract stands if the game is played within ``postponement_window_hours``;
    # otherwise ``cancellation`` applies.
    STANDS_IF_PLAYED_WITHIN_WINDOW = "STANDS_IF_PLAYED_WITHIN_WINDOW"
    # The market stays open however long the delay (Polymarket: "will remain open
    # until the game has been completed").
    STANDS_UNTIL_PLAYED = "STANDS_UNTIL_PLAYED"
    SETTLES_AT_FIXED_PRICE = "SETTLES_AT_FIXED_PRICE"


class CancellationRule(StrEnum):
    """Payout when the game is cancelled, abandoned early or not played in the window."""

    FIXED_PRICE = "FIXED_PRICE"  # Both sides paid ``cancellation_price`` (e.g. 50-50)
    VENUE_FAIR_VALUE = "VENUE_FAIR_VALUE"  # "Last fair price" / fair value settlement
    REFUND = "REFUND"  # Stake returned


class SettlementRules(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    overtime: OvertimeRule | None = None
    tie: TieRule | None = None
    tie_price: Decimal | None = None  # Paid per contract on a tie, for SETTLES_AT_FIXED_PRICE
    retirement: RetirementRule | None = None
    inactive_player: InactivePlayerRule | None = None
    postponement: PostponementRule | None = None
    postponement_window_hours: int | None = None
    cancellation: CancellationRule | None = None
    cancellation_price: Decimal | None = None  # For CancellationRule.FIXED_PRICE
    payout_per_contract_usd: Decimal | None = Decimal("1")
    settlement_source: str | None = None  # e.g. "official league result"

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def rules_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


# Terms that matter for equivalence. ``settlement_source`` is compared separately:
# two different but authoritative sources (for example, the league and a data
# vendor relaying it) are usually equivalent, so a mismatch there is reported
# under its own name and the matcher decides how strictly to treat it.
ECONOMIC_TERMS = (
    "overtime",
    "tie",
    "tie_price",
    "retirement",
    "inactive_player",
    "postponement",
    "postponement_window_hours",
    "cancellation",
    "cancellation_price",
    "payout_per_contract_usd",
)

# Parameters of another term: they exist only for some of its values, so
# ``None`` there means "not applicable" and is compared like any other value.
_PARAMETERS = frozenset({"tie_price", "postponement_window_hours", "cancellation_price"})


def rule_differences(a: SettlementRules, b: SettlementRules) -> list[str]:
    """Terms that differ, or that are unknown on either side."""
    diffs: list[str] = []
    for term in (*ECONOMIC_TERMS, "settlement_source"):
        va, vb = getattr(a, term), getattr(b, term)
        if term in _PARAMETERS:
            if va != vb:
                diffs.append(term)
        elif va is None or vb is None:
            # An unset source on both sides is not by itself a mismatch.
            if not (va is None and vb is None and term == "settlement_source"):
                diffs.append(f"{term}:unknown")
        elif va != vb:
            diffs.append(term)
    return diffs
