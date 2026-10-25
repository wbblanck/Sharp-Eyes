"""Depth-aware simulation of a follower's market buy against a captured book."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from sharp_eyes.capture.records import CaptureVenue, Level
from sharp_eyes.matching.nfl import Side
from sharp_eyes.pricing.fees import FeeModel

# Smallest tradable quantity in $1-payout contracts. Kalshi trades whole
# contracts; a Novig contract pays 1 cent, so 0.01 of a $1 contract; Polymarket
# US publishes ``minimumTradeQty`` per market.
DEFAULT_LOTS = {
    CaptureVenue.POLYMARKET: Decimal("0.01"),
    CaptureVenue.POLYMARKET_US: Decimal("1"),
    CaptureVenue.KALSHI: Decimal("1"),
    CaptureVenue.NOVIG: Decimal("0.01"),
}

_ONE = Decimal(1)


def buy_levels(bids: Sequence[Level], asks: Sequence[Level], side: Side) -> list[Level]:
    """Offers a buyer of ``side`` can take, cheapest first."""
    if side is Side.LONG:
        return sorted(asks)
    return sorted((_ONE - p, s) for p, s in bids)


def mid(bids: Sequence[Level], asks: Sequence[Level], side: Side) -> Decimal | None:
    if not bids or not asks:
        return None
    m = (max(p for p, _ in bids) + min(p for p, _ in asks)) / 2
    return m if side is Side.LONG else _ONE - m


@dataclass(frozen=True)
class SimFill:
    qty: Decimal
    cost: Decimal  # Contract cost before fees
    fee: Decimal
    complete: bool  # The whole stake was spent before the book ran out
    levels: int
    best_price: Decimal

    @property
    def avg_price(self) -> Decimal:
        return self.cost / self.qty

    @property
    def effective_price(self) -> Decimal:
        """Cost per contract including fees: the follower's break-even probability."""
        return (self.cost + self.fee) / self.qty


def simulate_buy(
    levels: Sequence[Level],
    stake_usd: Decimal,
    *,
    lot: Decimal,
    fees: FeeModel,
    in_play: bool,
) -> SimFill | None:
    """Spend up to ``stake_usd`` on contracts, cheapest first, in whole lots.

    Fees are charged on top of the stake. Returns ``None`` when not even one
    lot can be bought (empty book, or the best offer costs more than the stake).
    """
    budget = stake_usd
    pieces: list[tuple[Decimal, Decimal]] = []
    exhausted = True
    for price, size in levels:
        if price <= 0 or price >= 1 or size <= 0:
            continue
        affordable = ((budget / price) / lot).to_integral_value(rounding=ROUND_DOWN) * lot
        take = min(size, affordable)
        take = (take / lot).to_integral_value(rounding=ROUND_DOWN) * lot
        if take > 0:
            pieces.append((price, take))
            budget -= price * take
        if take < size:  # Budget ran out inside this level
            exhausted = False
            break
    if not pieces:
        return None
    qty = sum((q for _, q in pieces), Decimal(0))
    cost = sum((p * q for p, q in pieces), Decimal(0))
    return SimFill(
        qty=qty,
        cost=cost,
        fee=fees.fee(pieces, in_play=in_play),
        complete=not exhausted or budget < lot * pieces[-1][0],
        levels=len(pieces),
        best_price=pieces[0][0],
    )
