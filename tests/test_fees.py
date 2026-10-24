from __future__ import annotations

from decimal import Decimal as D

import pytest

from sharp_eyes.capture.records import CaptureVenue
from sharp_eyes.pricing.fees import FeeModelError, fee_model


def test_polymarket_uses_the_market_fee_schedule() -> None:
    model = fee_model(
        CaptureVenue.POLYMARKET,
        {"feeSchedule": {"rate": 0.03, "exponent": 1, "takerOnly": True}},
    )
    assert model.coefficient == D("0.03")
    # 100 shares at 0.40: 0.03 x 100 x 0.24
    assert model.fee([(D("0.40"), D("100"))], in_play=False) == D("0.72000")
    with pytest.raises(FeeModelError):
        fee_model(CaptureVenue.POLYMARKET, {"feeSchedule": {"rate": 0.03, "exponent": 2}})


@pytest.mark.parametrize(
    ("price", "fee"),
    [("0.10", "6.26"), ("0.65", "15.81"), ("0.50", "17.38")],  # Polymarket US fee table
)
def test_polymarket_us_rounds_the_order_to_the_cent(price: str, fee: str) -> None:
    model = fee_model(CaptureVenue.POLYMARKET_US, {"feeCoefficient": 0.0695})
    assert model.fee([(D(price), D("1000"))], in_play=False) == D(fee)


def test_kalshi_rounds_up() -> None:
    model = fee_model(CaptureVenue.KALSHI, {})
    assert model.fee([(D("0.50"), D("1"))], in_play=False) == D("0.0175")
    assert model.fee([(D("0.60"), D("20"))], in_play=False) == D("0.3360")
    assert model.fee([(D("0.33"), D("1"))], in_play=False) == D("0.0155")  # 0.015477 up


def test_novig_charges_only_in_play() -> None:
    model = fee_model(CaptureVenue.NOVIG, {"fee": {"coefficient": "0.06", "charged": "WHEN_LIVE"}})
    fills = [(D("0.50"), D("100"))]
    assert model.fee(fills, in_play=False) == 0
    assert model.fee(fills, in_play=True) == D("1.50000")
    with pytest.raises(FeeModelError):
        fee_model(CaptureVenue.NOVIG, {"fee": {"charged": "SOMETIMES"}})
