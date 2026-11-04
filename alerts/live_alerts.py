"""Post new pre-match bets by the frozen tennis list to Will's Discord channel.

Run hourly (Will, 4 Nov 2026):

    python3 live_alerts.py

Reads each list wallet's latest trades from Polymarket's Data API, keeps BUYs in
ATP/WTA markets placed before the market's listed start, and posts one message
per new pick (market and side), with the sharp's price and size and the best
price on offer now. A pick whose market list wallets have backed on both sides
is flagged, since the paper test skips those. Nothing is bought.

State (what was already posted) lives in alerts-state.json next to this file,
or at $ALERTS_STATE. The webhook link is read from $DISCORD_WEBHOOK, else from
.discord-webhook next to this file; it is a secret, keep it out of the repo and
out of notes. With no state yet, it looks back $FIRST_LOOKBACK_S seconds
(default 3 hours).

GitHub Actions (Will, 4 Nov 2026): .github/workflows/tennis-alerts.yml runs
this every 5 minutes with the webhook as a repository secret.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from venues import Venues  # noqa: E402
STATE = Path(os.environ.get("ALERTS_STATE") or HERE / "alerts-state.json")
DATA = "https://data-api.polymarket.com/v2/trades"
GAMMA = "https://gamma-api.polymarket.com/markets"
CLOB = "https://clob.polymarket.com/book"
ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "sharp-eyes", "Content-Type": "application/json"}


def get(url: str, params: dict) -> object:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params, doseq=True)}", headers=UA)
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
    return None


def post(webhook: str, text: str) -> None:
    body = json.dumps({"content": text[:1990]}).encode()
    for attempt in range(4):
        try:
            urllib.request.urlopen(urllib.request.Request(webhook, data=body, headers=UA), timeout=30)
            time.sleep(1.0)  # Discord webhooks throttle bursts
            return
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def best_ask(token: str) -> float | None:
    try:
        book = get(CLOB, {"token_id": token})
    except urllib.error.HTTPError:
        return None  # closed market: no book
    asks = [float(a["price"]) for a in (book or {}).get("asks") or []]
    return min(asks) if asks else None


def card(t: dict, m: dict, start: datetime, st: dict | None, venues: Venues, sides: dict) -> str:
    """One Discord message: the pick, the sharp, the best price to copy it, and risks."""
    outcomes = json.loads(m.get("outcomes") or "[]")
    tokens = json.loads(m.get("clobTokenIds") or "[]")
    pick = outcomes[t["k"]] if t["k"] < len(outcomes) else t["outcome"]
    q = t["price"] if t["side"] == "BUY" else 1 - t["price"]
    stake = t["size"] * q
    placed = datetime.fromtimestamp(t["timestamp"], UTC).astimezone(ET)
    tour, _, players = t["title"].rpartition(": ")
    kind = m.get("sportsMarketType") or ""
    if kind == "moneyline":
        head = f"**{pick}** to win | {players}{f' ({tour})' if tour else ''}"
    else:  # the question already names the players
        head = f"**{pick}** ({m.get('question') or kind})"
    money = (lambda x: f"${x:,.2f}") if stake < 10 else (lambda x: f"${x:,.0f}")
    lines = [
        head,
        f"Starts {start.astimezone(ET):%a %b %d %I:%M %p} ET",
    ]
    usual = ""
    if st and float(st["matches"]):
        avg = float(st["pre_match_stake"]) / float(st["matches"])
        usual = f" ({stake / avg:.1f}x their average stake per match, ${avg:,.0f})"
    lines.append(f"Sharp `{t['proxy_wallet'][:10]}` paid {q * 100:.0f}c, first fill {money(stake)} at {placed:%I:%M %p} ET{usual}")
    if st:
        lines.append(
            f"Record (pre-match tennis, Oct 2025 to Oct 28, every loss counted): "
            f"{int(float(st['matches']))} matches, {float(st['win_rate']):.0%} won, "
            f"ROI {float(st['roi']):+.1%} on ${float(st['pre_match_stake']):,.0f}"
        )
    risks = []
    best = None
    if kind == "moneyline" and " vs " in players:
        a, b = players.split(" vs ", 1)
        try:
            quotes = venues.quotes(a, b, pick, start.timestamp())
        except Exception as err:  # a venue being down should not stop the alert
            quotes = []
            risks.append(f"venue prices unavailable ({type(err).__name__})")
        if quotes:
            best = quotes[0]
            for i, v in enumerate(quotes):
                price = f"{v['price'] * 100:.1f}c + {v['fee'] * 100:.1f}c fee = **{v['all_in'] * 100:.1f}c**"
                where = f"[{v['venue']}](<{v['link']}>)" if v["link"] else f"{v['venue']} (app)"
                lines.append(f"{'Best: ' if i == 0 else 'Also: '}{where} {price}")
        else:
            lines.append("Not found on Polymarket US, Kalshi or Novig right now")
    else:
        lines.append("Side bet: Polymarket US, Kalshi and Novig list match winners only")
    ask = best_ask(tokens[t["k"]]) if t["k"] < len(tokens) else None
    slug = t.get("event_slug") or ""
    intl = f"[Polymarket international](<https://polymarket.com/event/{slug}>)" if slug else "Polymarket international"
    if ask is not None:  # polymarket.com/event/<slug> opens the match page (checked 4 Nov 2026)
        lines.append(f"{intl} (view only) now {ask * 100:.0f}c")
    elif slug:
        lines.append(f"{intl} (view only)")
    ref = best["all_in"] if best else ask
    if ref is not None and ref - q >= 0.02:
        risks.append(f"price is {(ref - q) * 100:.0f}c worse than the sharp paid")
    if len(sides.get(t["condition_id"], [])) > 1:
        risks.append("list wallets are on both sides (the paper test skips this)")
    if stake < 50:
        risks.append(f"small stake ({money(stake)})")
    if abs(q - 0.5) <= 0.02 and kind != "moneyline":
        risks.append("near 50c in a side market; check the match is still on")
    if risks:
        lines.append(":warning: " + "; ".join(risks))
    return "\n".join(lines)


def main() -> None:
    wallets = [r["wallet"] for r in csv.DictReader(open(HERE / "frozen-list-2026-10-29.csv"))]
    webhook = os.environ.get("DISCORD_WEBHOOK", "").strip() or (HERE / ".discord-webhook").read_text().strip()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    run_at = time.time()
    since = state.get("since", run_at - float(os.environ.get("FIRST_LOOKBACK_S") or 3 * 3600))
    posted: dict[str, list] = state.get("posted", {})  # "cid:k" -> [ts, wallet]
    sides: dict[str, list[int]] = state.get("sides", {})  # cid -> sides backed
    new: list[dict] = []

    def latest(w: str) -> list[dict]:
        return (get(DATA, {"user": w, "limit": 50, "taker_only": "false"}) or {}).get("data") or []

    with ThreadPoolExecutor(4) as pool:  # 4 at a time; get() backs off on 429
        batches = list(pool.map(latest, wallets))
    for rows in batches:
        for t in rows:
            slug = t.get("event_slug") or ""
            if t["timestamp"] <= since or not slug.startswith(("atp-", "wta-")):
                continue
            k = t["outcome_index"] if t["side"] == "BUY" else 1 - t["outcome_index"]
            new.append({**t, "k": k})
    meta: dict[str, dict] = {}
    cids = sorted({t["condition_id"] for t in new})
    for i in range(0, len(cids), 20):
        for m in get(GAMMA, {"condition_ids": cids[i : i + 20], "limit": 20}) or []:
            meta[m["conditionId"]] = m
    out = []
    for t in sorted(new, key=lambda t: t["timestamp"]):
        m = meta.get(t["condition_id"])
        raw = (m or {}).get("gameStartTime") or ""
        if m is None or not raw:
            continue
        start = datetime.fromisoformat(raw.replace(" ", "T").replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if t["timestamp"] >= start.timestamp():
            continue  # in-play, or unknown market: the paper test copies pre-match only
        cid, k = t["condition_id"], t["k"]
        sides.setdefault(cid, [])
        if k not in sides[cid]:
            sides[cid].append(k)
        key = f"{cid}:{k}"
        if key in posted:
            continue
        posted[key] = [t["timestamp"], t["proxy_wallet"]]
        out.append((t, m, start))
    stats = {r["wallet"]: r for r in csv.DictReader(open(HERE / "frozen-list-2026-10-29.csv"))}
    venues = Venues()
    for t, m, start in out:
        post(webhook, card(t, m, start, stats.get(t["proxy_wallet"]), venues, sides))
    STATE.write_text(json.dumps({"since": run_at - 600, "posted": posted, "sides": sides}))
    print(f"{len(new)} new list trades, {len(out)} new picks posted")


if __name__ == "__main__":
    main()
