"""Find a tennis match-winner pick on Polymarket US, Kalshi and Novig, and price it.

Price = what a taker pays now per $1 of payout, plus the taker fee:
* Polymarket US: book /v1/markets/{slug}/book; buying the "long" side lifts its
  offers, the other side costs 1 - best long bid. Fee feeCoefficient x p(1-p)
  (0.0695 on tennis match winners, read from the market).
* Kalshi: yes_ask_dollars of the player's market. Fee 0.07 x p(1-p) (series fee
  multiplier 1, checked 4 Nov 2026 for KXATPMATCH and KXWTAMATCH).
* Novig: every order buys one outcome, so taking a side costs 1 - best resting
  price on the other outcome. Fee only while live (charged WHEN_LIVE), so 0
  before the match.
A quote with under $10 of payout behind it is ignored. Matches are found by
both players' last names and a start within 36 hours.

Links: polymarket.us/event/<slug> and kalshi.com/events/<EVENT_TICKER> (both
checked 4 Nov 2026). Novig has no public web link for a market; it is app only.
"""

from __future__ import annotations

import json
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

UA = {"User-Agent": "sharp-eyes"}
PMUS = "https://gateway.polymarket.us/v1"
KALSHI = "https://external-api.kalshi.com/trade-api/v2"
NOVIG = "https://api.novig.com/v3/public/catalog"
KALSHI_SERIES = ("KXATPMATCH", "KXWTAMATCH", "KXATPCHALLENGERMATCH", "KXWTACHALLENGERMATCH")
MIN_PAYOUT = 10.0


def _get(url: str, params: dict | None = None, pause: float = 0.0) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params, doseq=True)}" if params else url
    for attempt in range(4):
        try:
            data = json.load(urllib.request.urlopen(urllib.request.Request(full, headers=UA), timeout=40))
            time.sleep(pause)
            return data
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
    return {}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return "".join(ch if ch.isalnum() else " " for ch in text)


def last(name: str) -> str:
    words = norm(name.split(",")[0] if "," in name else name).split()
    return words[-1] if words else ""


def ts(raw: str | None) -> float:
    if not raw:
        return 0.0
    return datetime.fromisoformat(raw.replace(" ", "T").replace("Z", "+00:00")).timestamp()


class Venues:
    """Catalogs are loaded once per run, books per pick."""

    def __init__(self) -> None:
        self._pmus: list[dict] | None = None
        self._kalshi: list[dict] | None = None
        self._novig: list[tuple[dict, dict]] | None = None

    def pmus(self) -> list[dict]:
        if self._pmus is None:
            self._pmus = []
            for off in range(0, 20000, 500):
                page = _get(f"{PMUS}/events", {"limit": 500, "offset": off, "active": "true", "closed": "false"}).get("events") or []
                for e in page:
                    for m in e.get("markets") or []:
                        if m.get("sportsMarketType") == "tennis_match_winner":
                            self._pmus.append({"event": e, "market": m})
                if len(page) < 500:
                    break
        return self._pmus

    def kalshi(self) -> list[dict]:
        if self._kalshi is None:
            self._kalshi = []
            for series in KALSHI_SERIES:
                cursor = ""
                while True:
                    params = {"series_ticker": series, "status": "open", "limit": 200, "with_nested_markets": "true"}
                    if cursor:
                        params["cursor"] = cursor
                    body = _get(f"{KALSHI}/events", params, pause=0.25)
                    self._kalshi.extend(body.get("events") or [])
                    cursor = body.get("cursor") or ""
                    if not cursor:
                        break
        return self._kalshi

    def novig(self) -> list[tuple[dict, dict]]:
        if self._novig is None:
            self._novig = []
            for league in ("ATP", "WTA"):
                events, markets, after = {}, [], ""
                for kind, sink in (("events", None), ("markets", markets)):
                    after = ""
                    while True:
                        params = {"league": league, "limit": 100}
                        if after:
                            params["after"] = after
                        body = _get(f"{NOVIG}/{kind}", params, pause=0.3)
                        for item in body.get("items") or []:
                            if sink is None:
                                events[item["eventId"]] = item
                            elif item.get("marketType") == "MONEY":
                                sink.append(item)
                        after = body.get("next") or ""
                        if not after:
                            break
                self._novig.extend((events[m["eventId"]], m) for m in markets if m["eventId"] in events)
        return self._novig

    def quotes(self, player_a: str, player_b: str, pick: str, start: float) -> list[dict]:
        """All-in price of `pick` on each venue that lists this match."""
        la, lb, lp = last(player_a), last(player_b), last(pick)
        out: list[dict] = []

        def same(text: str, when: float) -> bool:
            words = set(norm(text).split())
            return la in words and lb in words and abs(when - start) < 36 * 3600

        for row in self.pmus():
            e, m = row["event"], row["market"]
            if not same(e.get("title", ""), ts(m.get("gameStartTime") or e.get("startTime"))):
                continue
            sides = m.get("marketSides") or []
            side = next((s for s in sides if lp in norm(s.get("description", "")).split()), None)
            if side is None:
                continue
            book = _get(f"{PMUS}/markets/{m['slug']}/book").get("marketData") or {}
            if side.get("long"):
                levels = [(float(o["px"]["value"]), float(o["qty"])) for o in book.get("offers") or []]
            else:
                levels = [(1 - float(b["px"]["value"]), float(b["qty"])) for b in book.get("bids") or []]
            levels = sorted(p for p in levels if p[1] >= MIN_PAYOUT)
            if levels:
                p = levels[0][0]
                fee = float(m.get("feeCoefficient") or 0.0695) * p * (1 - p)
                out.append({"venue": "Polymarket US", "price": p, "fee": fee, "all_in": p + fee,
                            "link": f"https://polymarket.us/event/{e['slug']}"})  # fmt: skip
            break
        for e in self.kalshi():
            mk = e.get("markets") or []
            when = max((ts(m.get("occurrence_datetime") or m.get("expected_expiration_time")) for m in mk), default=0.0)
            if not same(e.get("title", "") + " " + e.get("sub_title", ""), when):
                continue
            m = next((m for m in mk if lp in norm(m.get("yes_sub_title") or m.get("title", "")).split()), None)
            if m is None or float(m.get("yes_ask_size_fp") or 0) < MIN_PAYOUT:
                continue
            p = float(m.get("yes_ask_dollars") or 0)
            if 0 < p < 1:
                fee = 0.07 * p * (1 - p)
                out.append({"venue": "Kalshi", "price": p, "fee": fee, "all_in": p + fee,
                            "link": f"https://kalshi.com/events/{e['event_ticker']}"})  # fmt: skip
            break
        for e, m in self.novig():
            if not same(e.get("description", ""), (e.get("startsTs") or 0) / 1000):
                continue
            outs = m.get("outcomes") or []
            mine = next((o for o in outs if lp in norm(o.get("name", "")).split()), None)
            other = next((o for o in outs if o is not mine), None)
            if mine is None or other is None:
                continue
            book = _get(f"{NOVIG}/markets/{m['marketId']}/book", pause=0.3).get("orders") or {}
            rest = [(float(o["price"]), o["qty"] / 100) for o in book.get(other["outcomeId"]) or []]
            rest = [r for r in rest if r[1] >= MIN_PAYOUT]
            if rest:
                p = 1 - max(r[0] for r in rest)
                out.append({"venue": "Novig", "price": p, "fee": 0.0, "all_in": p, "link": None})
            break
        return sorted(out, key=lambda q: q["all_in"])
