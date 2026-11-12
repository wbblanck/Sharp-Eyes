"""Save Novig's currently listed ATP/WTA markets (names, outcomes, start times).

Novig's daily trade files (data.novig.com) carry only market and outcome ids,
and its public catalog drops a market once it settles, so the names have to
be saved while a match is still listed. Run at least daily:

    python3 novig_listings.py

Writes novig-listings/<UTC timestamp>.json next to this file.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

API = "https://api.novig.com/v3/public/catalog"
OUT = Path(__file__).parent / "novig-listings"


def pages(path: str, params: dict[str, str]) -> list[dict]:
    items: list[dict] = []
    params = dict(params)
    while True:
        url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "sharp-eyes"})
        body = json.load(urllib.request.urlopen(req, timeout=60))
        items.extend(body.get("items") or [])
        if not body.get("next"):
            return items
        params["after"] = body["next"]
        time.sleep(0.5)  # public routes throttle per IP


def main() -> None:
    snap = {"taken_at": datetime.now(UTC).isoformat(), "leagues": {}}
    for league in ("ATP", "WTA"):
        snap["leagues"][league] = {
            "events": pages("events", {"league": league, "limit": "100"}),
            "markets": pages("markets", {"league": league, "limit": "100"}),
        }
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(snap))
    counts = {k: (len(v["events"]), len(v["markets"])) for k, v in snap["leagues"].items()}
    print(f"saved {path}: (events, markets) per league {counts}")


if __name__ == "__main__":
    main()
