from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal as D

import httpx
import pytest

from sharp_eyes.capture.http import VenueHttpError, retry_delay
from sharp_eyes.capture.records import BookSnapshot, CaptureVenue, aggregate_levels, complement
from tests.conftest import json_response, mock_http


def test_aggregate_levels_sums_sorts_and_truncates() -> None:
    levels = [(D("0.40"), D("5")), (D("0.42"), D("1")), (D("0.40"), D("2")), (D("0.30"), D("0"))]
    assert aggregate_levels(levels, descending=True, max_levels=5) == (
        (D("0.42"), D("1")),
        (D("0.40"), D("7")),
    )
    assert aggregate_levels(levels, descending=False, max_levels=1) == ((D("0.40"), D("7")),)


def test_complement_turns_opposite_bids_into_asks_best_first() -> None:
    no_bids = ((D("0.39"), D("10")), (D("0.38"), D("4")))  # best first
    assert complement(no_bids) == ((D("0.61"), D("10")), (D("0.62"), D("4")))


def test_book_hash_ignores_time_but_not_content() -> None:
    t1, t2 = datetime(2026, 10, 24, tzinfo=UTC), datetime(2026, 10, 25, tzinfo=UTC)
    a = BookSnapshot(CaptureVenue.KALSHI, "m", "k", t1, ((D("0.5"), D("1")),), ())
    b = BookSnapshot(CaptureVenue.KALSHI, "m", "k", t2, ((D("0.5"), D("1")),), ())
    c = BookSnapshot(CaptureVenue.KALSHI, "m", "k", t2, ((D("0.5"), D("2")),), ())
    assert a.content_hash() == b.content_hash() != c.content_hash()
    assert a.best_bid == D("0.5") and a.best_ask is None


def test_retry_delay_honours_retry_after() -> None:
    assert retry_delay(1, "3") == 3.0
    assert 0 < retry_delay(3, None) <= 2.0


async def test_http_retries_429_then_succeeds() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            return json_response({"msg": "slow down"}, 429)
        return json_response({"ok": True})

    http = mock_http(handler)
    resp = await http.get("/x")
    assert resp.data == {"ok": True} and len(calls) == 3 and http.retries == 2


async def test_http_raises_on_non_retryable_status() -> None:
    http = mock_http(lambda r: json_response({"code": "MARKET_NOT_FOUND"}, 404))
    with pytest.raises(VenueHttpError) as exc:
        await http.get("/x")
    assert exc.value.status == 404
