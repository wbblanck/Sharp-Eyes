"""Steelers @ Saints (2026-10-25) as each venue listed it, parsed by the capture adapters."""

from __future__ import annotations

import json
from pathlib import Path

from sharp_eyes.capture.records import EventRecord, MarketRecord
from sharp_eyes.capture.venues import kalshi, novig, polymarket, polymarket_us

FIXTURE = Path(__file__).parent / "fixtures" / "nfl_pit_no.json"


def load_raw() -> dict:  # type: ignore[type-arg]
    return json.loads(FIXTURE.read_text())  # type: ignore[no-any-return]


def load_catalog() -> tuple[list[EventRecord], list[MarketRecord]]:
    raw = load_raw()
    events: list[EventRecord] = []
    markets: list[MarketRecord] = []
    for parse, payload in (
        (polymarket.parse_event, raw["polymarket"]),
        (polymarket_us.parse_event, raw["polymarket_us"]),
        *((kalshi.parse_event, ev) for ev in raw["kalshi"].values()),
    ):
        event, found = parse(payload)
        events.append(event)
        markets += found
    events.append(novig.parse_event(raw["novig"]["event"]))
    markets += [novig.parse_market(m) for m in raw["novig"]["markets"]]
    return events, markets
