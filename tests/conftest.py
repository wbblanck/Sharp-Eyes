from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, create_engine, text

from sharp_eyes.capture.http import VenueHttp

Handler = Callable[[httpx.Request], httpx.Response]


def json_response(
    body: Any, status: int = 200, headers: dict[str, str] | None = None
) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(body).encode(), headers=headers)


def mock_http(handler: Handler, base_url: str = "https://test.invalid") -> VenueHttp:
    return VenueHttp(
        "TEST",
        base_url,
        rate_per_second=1000,
        burst=1000,
        transport=httpx.MockTransport(handler),
    )


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sharp_eyes.capture.http.retry_delay", lambda *a, **k: 0.0)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ.get("SHARP_EYES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SHARP_EYES_TEST_DATABASE_URL not set")
    eng = create_engine(url)
    from sharp_eyes.capture.schema import SCHEMA, metadata

    with eng.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def clean_engine(engine: Engine) -> Engine:
    from sharp_eyes.capture.schema import metadata

    with engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())
    return engine
