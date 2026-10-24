"""Decimal helpers for money and prices. Floats are never used for accounting."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

CENT = Decimal("0.01")
# Prices are probabilities in [0, 1]. Venues quote to at most 4 dp today
# (Kalshi subpenny); store 6 dp to leave room.
PRICE_QUANTUM = Decimal("0.000001")


def to_decimal(value: str | int | Decimal) -> Decimal:
    """Convert to Decimal. Floats are rejected so binary rounding never leaks in."""
    if isinstance(value, float):  # pragma: no cover - guarded by typing too
        raise TypeError("floats are not accepted for money or prices; pass a string")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"not a decimal: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"not a finite decimal: {value!r}")
    return result


def to_price(value: str | int | Decimal) -> Decimal:
    price = to_decimal(value)
    if not Decimal(0) <= price <= Decimal(1):
        raise ValueError(f"price must be within [0, 1]: {price}")
    return price.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_EVEN)


def round_usd(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)
