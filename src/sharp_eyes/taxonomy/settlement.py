"""Settlement-rule representation (spec 4.2, 7.1).

Two contracts that agree on event, selection, line and period can still be
different bets if they settle differently: overtime, retirement and inactive
player rules all change the payout. ``SettlementRules`` captures those terms
explicitly; :func:`rule_differences` lists every term on which two rule sets
disagree or cannot be compared, which the contract matcher (SC-011) uses to
decide between EXACT, EQUIVALENT_WITH_RULE_DIFFERENCE and AMBIGUOUS.

``None`` always means *unknown*, never a default. Unknown terms are reported
as differences because equivalence cannot be shown.
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
    LOSES = "LOSES"  # Both sides of a binary contract cannot win, so the selected side loses
    IMPOSSIBLE = "IMPOSSIBLE"  # Half-point line or format with no ties
    SETTLES_AT_FIXED_PRICE = "SETTLES_AT_FIXED_PRICE"  # e.g. both outcomes settle at 0.50


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
    STANDS_IF_PLAYED_WITHIN_WINDOW = "STANDS_IF_PLAYED_WITHIN_WINDOW"
    SETTLES_AT_FIXED_PRICE = "SETTLES_AT_FIXED_PRICE"


class SettlementRules(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    overtime: OvertimeRule | None = None
    tie: TieRule | None = None
    retirement: RetirementRule | None = None
    inactive_player: InactivePlayerRule | None = None
    postponement: PostponementRule | None = None
    postponement_window_hours: int | None = None
    void_settlement_price: Decimal | None = None  # Price paid per contract on a void, if any
    payout_per_contract_usd: Decimal | None = Decimal("1")
    settlement_source: str | None = None  # e.g. "official league box score"

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def rules_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


# Terms that matter for equivalence. ``settlement_source`` is compared separately:
# two different but authoritative sources (for example, the league and a data
# vendor relaying it) are usually equivalent, so a mismatch there is reported
# under its own name and the matcher decides how strictly to treat it.
_ECONOMIC_TERMS = (
    "overtime",
    "tie",
    "retirement",
    "inactive_player",
    "postponement",
    "postponement_window_hours",
    "void_settlement_price",
    "payout_per_contract_usd",
)


def rule_differences(a: SettlementRules, b: SettlementRules) -> list[str]:
    """Terms that differ, or that are unknown on either side."""
    diffs: list[str] = []
    for term in (*_ECONOMIC_TERMS, "settlement_source"):
        va, vb = getattr(a, term), getattr(b, term)
        if va is None or vb is None:
            # Unknown on either side means equivalence cannot be shown, except for
            # optional parameters that both sides leave unset.
            if not (va is None and vb is None and term in _OPTIONAL_WHEN_BOTH_UNSET):
                diffs.append(f"{term}:unknown")
        elif va != vb:
            diffs.append(term)
    return diffs


# Terms whose absence on both sides is not by itself a mismatch.
_OPTIONAL_WHEN_BOTH_UNSET = frozenset(
    {"postponement_window_hours", "void_settlement_price", "settlement_source"}
)
