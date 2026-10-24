"""Smoke tests against the real venue APIs. Opt in with ``pytest -m live``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sharp_eyes.capture.http import VenueHttp
from sharp_eyes.capture.venues import kalshi, novig, polymarket, polymarket_us
from sharp_eyes.capture.venues.base import VenueAdapter

pytestmark = pytest.mark.live


def adapters() -> list[VenueAdapter]:
    return [
        polymarket.PolymarketAdapter(
            VenueHttp("POLYMARKET", polymarket.GAMMA, rate_per_second=4),
            data_http=VenueHttp("POLYMARKET", polymarket.DATA, rate_per_second=4),
            clob_http=VenueHttp("POLYMARKET", polymarket.CLOB, rate_per_second=4),
        ),
        polymarket_us.PolymarketUSAdapter(
            VenueHttp("POLYMARKET_US", polymarket_us.GATEWAY, rate_per_second=4)
        ),
        kalshi.KalshiAdapter(VenueHttp("KALSHI", kalshi.API, rate_per_second=2)),
        novig.NovigAdapter(VenueHttp("NOVIG", novig.API, rate_per_second=2)),
    ]


@pytest.mark.parametrize("adapter", adapters(), ids=lambda a: a.venue.value)
async def test_catalog_and_books(adapter: VenueAdapter) -> None:
    now = datetime.now(UTC)
    catalog = await adapter.fetch_catalog(now - timedelta(hours=6), now + timedelta(days=8))
    core = [m for m in catalog.markets if m.is_core]
    if not core:
        pytest.skip(f"{adapter.venue}: no NFL games listed right now")
    books = await adapter.fetch_books(core[:3])
    assert books  # Thin alt lines can be empty, so only check that books came back
    await adapter.aclose()
