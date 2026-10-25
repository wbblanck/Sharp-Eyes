"""Taker fee models per venue (checked against each venue's fee docs, 2026-10-24).

All four venues charge takers a fee of the same shape, ``coefficient x C x p(1-p)``
for C $1-payout contracts at price p, but they differ in the coefficient, in
when the fee applies and in rounding:

========== ======================== ==================== ==========================
Venue      coefficient              applies              rounding
========== ======================== ==================== ==========================
Polymarket market ``feeSchedule.rate`` always (takers)     5 dp
PM US      market ``feeCoefficient`` always (takers)     cent, banker's, per order
           (0.0695 standard)
Kalshi     0.07 x series multiplier always (takers)     up to $0.0001, per fill
Novig      market ``fee.coefficient`` only while in-game  half up to $0.00001
           (0.06)                   (``WHEN_LIVE``)
========== ======================== ==================== ==========================

A follower crossing the spread is always a taker, so maker fees and rebates
are ignored. A fee model is read from the listing's raw payload where the venue
publishes it there, so a change in the venue's schedule follows automatically.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from typing import Any

from sharp_eyes.capture.records import CaptureVenue

POLYMARKET_SPORTS_RATE = Decimal("0.05")  # Used only when a market has no feeSchedule
POLYMARKET_US_THETA = Decimal("0.0695")
KALSHI_TAKER = Decimal("0.07")
NOVIG_COEFFICIENT = Decimal("0.06")

_ONE = Decimal(1)


class FeeModelError(ValueError):
    """The listing's fee terms are not ones this module understands."""


@dataclass(frozen=True)
class FeeModel:
    venue: CaptureVenue
    coefficient: Decimal
    only_in_play: bool = False
    quantum: Decimal = Decimal("0.00001")
    rounding: str = ROUND_HALF_EVEN
    per_fill: bool = True  # False: round the order's total once (Polymarket US)

    def fee(self, fills: Sequence[tuple[Decimal, Decimal]], *, in_play: bool) -> Decimal:
        """Taker fee in USD for an order filled as ``(price, contracts)`` pieces."""
        if self.only_in_play and not in_play:
            return Decimal(0)
        exact = [self.coefficient * qty * p * (_ONE - p) for p, qty in fills]
        if self.per_fill:
            return sum(
                (x.quantize(self.quantum, rounding=self.rounding) for x in exact), Decimal(0)
            )
        return sum(exact, Decimal(0)).quantize(self.quantum, rounding=self.rounding)


def fee_model(
    venue: CaptureVenue, raw: Mapping[str, Any], *, kalshi_multiplier: Decimal = _ONE
) -> FeeModel:
    """The taker fee model for one listing, from its raw catalog payload."""
    if venue is CaptureVenue.POLYMARKET:
        schedule = raw.get("feeSchedule")
        if isinstance(schedule, Mapping):
            if Decimal(str(schedule.get("exponent", 1))) != 1:
                raise FeeModelError(f"unsupported Polymarket fee exponent: {schedule}")
            rate = Decimal(str(schedule.get("rate", 0)))
        else:
            rate = POLYMARKET_SPORTS_RATE if raw.get("feesEnabled", True) else Decimal(0)
        return FeeModel(venue, rate, quantum=Decimal("0.00001"))
    if venue is CaptureVenue.POLYMARKET_US:
        theta = Decimal(str(raw.get("feeCoefficient") or POLYMARKET_US_THETA))
        return FeeModel(venue, theta, quantum=Decimal("0.01"), per_fill=False)
    if venue is CaptureVenue.KALSHI:
        return FeeModel(
            venue, KALSHI_TAKER * kalshi_multiplier, quantum=Decimal("0.0001"),
            rounding=ROUND_CEILING,
        )  # fmt: skip
    if venue is CaptureVenue.NOVIG:
        fee = raw.get("fee") or {}
        charged = fee.get("charged", "WHEN_LIVE")
        if charged not in ("WHEN_LIVE", "ALWAYS"):
            raise FeeModelError(f"unsupported Novig fee schedule: {fee}")
        return FeeModel(
            venue,
            Decimal(str(fee.get("coefficient") or NOVIG_COEFFICIENT)),
            only_in_play=charged == "WHEN_LIVE",
            quantum=Decimal("0.00001"),
            rounding=ROUND_HALF_UP,
        )
    raise FeeModelError(f"no fee model for {venue}")
