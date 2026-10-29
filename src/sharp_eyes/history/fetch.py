"""Download settled Polymarket games (NFL, tennis) and all their fills to a local cache.

Layout under ``data_dir`` (one pair of files per game, written atomically):

* ``events/<event_id>.json``: the Gamma event, trimmed to what scoring needs.
* ``fills/<event_id>.jsonl.gz``: one compact fill per line,
  ``[ts, wallet, condition_id, outcome_index, side, price, size, taker]``.

A game is downloaded once; re-running only fetches games not cached yet, so
the cache can be topped up weekly from any laptop. Tennis "games" are matches.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sharp_eyes.capture.http import VenueHttp
from sharp_eyes.capture.venues.base import gather_limited
from sharp_eyes.capture.venues.polymarket import DATA, GAMMA, TRADE_PAGE, keyed_rows

log = logging.getLogger(__name__)

# Gamma series per sport, keyed by season (NFL) or tour (tennis). gamma
# /sports lists only each sport's current series.
SPORT_SERIES: dict[str, dict[str, str]] = {
    "nfl": {"2025": "10187", "2026": "12185"},
    "tennis": {
        "atp": "10365",
        "wta": "10366",
        "itf": "11634",
        "atp-doubles": "11632",
        "wta-doubles": "11633",
    },  # fmt: skip
}
# Series fetched when none are named: tennis ITF and doubles markets are tiny.
DEFAULT_SERIES: dict[str, tuple[str, ...]] = {"nfl": ("2025", "2026"), "tennis": ("atp", "wta")}
SEASON_SERIES = SPORT_SERIES["nfl"]

MARKET_KEYS = (
    "conditionId",
    "question",
    "sportsMarketType",
    "line",
    "outcomes",
    "outcomePrices",
    "umaResolutionStatus",
    "closed",
    "closedTime",
    "gameStartTime",
    "feesEnabled",
    "feeSchedule",
)


def is_game_event(raw: dict[str, Any], sport: str = "nfl") -> bool:
    """NFL games are "Away vs. Home"; props and scorer events add " - ...".

    Tennis matches are "Tournament: Player vs Player" with a moneyline market.
    """
    title = raw.get("title") or ""
    if sport == "tennis":
        markets = raw.get("markets") or []
        return " vs " in title and any(m.get("sportsMarketType") == "moneyline" for m in markets)
    return " vs. " in title and " - " not in title


def trim_event(raw: dict[str, Any], season: str, sport: str = "nfl") -> dict[str, Any]:
    return {
        "id": str(raw["id"]),
        "sport": sport,
        "season": season,
        "title": raw.get("title") or "",
        "slug": raw.get("slug") or "",
        "startTime": raw.get("startTime") or raw.get("endDate"),
        "markets": [{k: m.get(k) for k in MARKET_KEYS} for m in raw.get("markets") or []],
    }


def compact_fill(row: dict[str, Any], taker: bool) -> list[Any]:
    return [
        int(row["timestamp"]),
        (row.get("proxy_wallet") or "").lower(),
        row.get("condition_id") or "",
        int(row.get("outcome_index") or 0),
        row.get("side") or "",
        float(row["price"]),
        float(row["size"]),
        1 if taker else 0,
    ]


def merge_passes(
    all_rows: Sequence[dict[str, Any]], taker_rows: Sequence[dict[str, Any]]
) -> list[list[Any]]:
    """Every fill (maker rows included), flagged when it was the taker side."""
    taker_keys = {key for key, _ in keyed_rows(taker_rows)}
    out = []
    for key, row in keyed_rows(all_rows):
        if row.get("price") is None or row.get("size") is None or not row.get("timestamp"):
            continue
        out.append(compact_fill(row, key in taker_keys))
    return out


@dataclass
class HistoryCache:
    root: Path

    @property
    def events_dir(self) -> Path:
        return self.root / "events"

    @property
    def fills_dir(self) -> Path:
        return self.root / "fills"

    def has(self, event_id: str) -> bool:
        return (self.fills_dir / f"{event_id}.jsonl.gz").exists() and (
            self.events_dir / f"{event_id}.json"
        ).exists()

    def event_ids(self) -> list[str]:
        if not self.events_dir.exists():
            return []
        return sorted(p.stem for p in self.events_dir.glob("*.json") if self.has(p.stem))

    def load_event(self, event_id: str) -> dict[str, Any]:
        data: dict[str, Any] = json.loads((self.events_dir / f"{event_id}.json").read_text())
        return data

    def load_fills(self, event_id: str) -> list[list[Any]]:
        with gzip.open(self.fills_dir / f"{event_id}.jsonl.gz", "rt") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def save(self, event: dict[str, Any], fills: Sequence[Sequence[Any]]) -> None:
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.fills_dir.mkdir(parents=True, exist_ok=True)
        eid = event["id"]
        fills_path = self.fills_dir / f"{eid}.jsonl.gz"
        tmp = fills_path.with_suffix(".tmp")
        with gzip.open(tmp, "wt") as fh:
            for f in fills:
                fh.write(json.dumps(f, separators=(",", ":")) + "\n")
        os.replace(tmp, fills_path)
        # The event file goes last: its presence marks the pair complete.
        ev_path = self.events_dir / f"{eid}.json"
        ev_tmp = ev_path.with_suffix(".tmp")
        ev_tmp.write_text(json.dumps(event))
        os.replace(ev_tmp, ev_path)


async def list_settled_games(
    gamma: VenueHttp, season: str, sport: str = "nfl", min_volume: float = 0.0
) -> list[dict[str, Any]]:
    """Settled games of one series, via keyset paging (/events refuses offsets
    past a few thousand, and a tennis tour has over ten thousand matches)."""
    series = SPORT_SERIES[sport][season]
    out: list[dict[str, Any]] = []
    params: dict[str, Any] = {"series_id": series, "closed": "true", "limit": 500}
    seen: set[str] = set()
    while True:
        resp = await gamma.get("/events/keyset", params=params)
        body = resp.data or {}
        page: list[dict[str, Any]] = body.get("events") or []
        new = [raw for raw in page if str(raw["id"]) not in seen]
        seen.update(str(raw["id"]) for raw in page)
        out.extend(
            trim_event(raw, season, sport)
            for raw in new
            if is_game_event(raw, sport) and float(raw.get("volume") or 0) >= min_volume
        )
        cursor = body.get("next_cursor")
        if not cursor or not new:
            return out
        params["after_cursor"] = cursor


async def _walk_all(data: VenueHttp, event_id: str, taker_only: bool) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "event_id": event_id,
        "limit": TRADE_PAGE,
        "taker_only": "true" if taker_only else "false",
    }
    rows: list[dict[str, Any]] = []
    while True:
        resp = await data.get("/v2/trades", params=params)
        body = resp.data or {}
        page: list[dict[str, Any]] = body.get("data") or []
        rows.extend(page)
        cursor = (body.get("pagination") or {}).get("next_cursor")
        if not cursor or not page:
            return rows
        params["cursor"] = cursor


async def fetch_event_fills(data: VenueHttp, event_id: str) -> list[list[Any]]:
    all_rows = await _walk_all(data, event_id, taker_only=False)
    taker_rows = await _walk_all(data, event_id, taker_only=True)
    return merge_passes(all_rows, taker_rows)


async def sync(
    cache: HistoryCache,
    seasons: Sequence[str],
    *,
    sport: str = "nfl",
    min_volume: float = 0.0,
    concurrency: int = 4,
    data_rate: float = 10.0,
    limit: int | None = None,
) -> tuple[int, int]:
    """Fetch every settled game not cached yet. Returns (fetched, already cached)."""
    gamma = VenueHttp("POLYMARKET", GAMMA, rate_per_second=4)
    data = VenueHttp("POLYMARKET", DATA, rate_per_second=data_rate, max_attempts=8)
    try:
        games: list[dict[str, Any]] = []
        for season in seasons:
            found = await list_settled_games(gamma, season, sport, min_volume)
            log.info("season %s: %d settled games", season, len(found))
            games.extend(found)
        todo = [g for g in games if not cache.has(g["id"])]
        cached = len(games) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        done = 0

        async def one(game: dict[str, Any]) -> None:
            nonlocal done
            fills = await fetch_event_fills(data, game["id"])
            cache.save(game, fills)
            done += 1
            log.info("[%d/%d] %s %s: %d fills", done, len(todo), game["id"], game["title"],
                     len(fills))  # fmt: skip

        results = await gather_limited(todo, one, concurrency)
        failed = [g["id"] for g, r in zip(todo, results, strict=True) if isinstance(r, Exception)]
        if failed:
            log.warning("%d games failed, re-run to retry: %s", len(failed), ", ".join(failed))
        return done, cached
    finally:
        await gamma.aclose()
        await data.aclose()


def run_sync(cache_dir: Path, seasons: Sequence[str], **kwargs: Any) -> tuple[int, int]:
    return asyncio.run(sync(HistoryCache(cache_dir), seasons, **kwargs))


__all__ = ["DEFAULT_SERIES", "SEASON_SERIES", "SPORT_SERIES", "HistoryCache", "run_sync", "sync"]
