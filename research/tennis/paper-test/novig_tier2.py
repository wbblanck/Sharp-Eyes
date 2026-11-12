"""Paper test of the Tier 2 pre-match match-winner wallets, priced on Novig (no fee pre-match).

Will chose this on 7 Nov 2026. Run from the Sharp-Eyes repo after the nightly
history-fetch (same cache as paper_test.py):

    uv run python research/tennis/paper-test/novig_tier2.py \
        data/paper-tennis

Rules:
* Wallets: tier2-list.csv, Tier 2 in "pre-match match winner" for their tour (ATP or
  WTA), picked only on trades before 2026-10-29 14:10 UTC. Only their picks in that tour.
* Matches listed to start after 2026-10-29 14:10 UTC. One bet per pick (match and
  player), timed on the earliest Tier 2 wallet's first pre-match buy. A match where
  Tier 2 wallets back both players is skipped (same as the main paper test).
* Novig copy price: the first Novig trade where a taker bought the same player, at
  least DELAY seconds after the wallet's trade, within 30 minutes and before the start.
  Novig charges takers no fee before the match (checked 30 Oct 2026). No such trade: no bet.
* For comparison, the same picks copied on Polymarket at the next printed trade, with
  the taker fee (the main paper test's rule).
* $5 a bet, settled at the Polymarket result; 50-50 counts as a void outside win-loss.
  Novig's own settlement of retirements is not checked.

Novig trade files (data.novig.com, one per ET day) are filtered to ATP/WTA match
winners and kept in novig-trades/; match and player names come from the daily
novig-listings/ snapshots, so a match listed and played between two snapshots is missed.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sharp_eyes.history.analyze import parse_markets, parse_ts, price_paths, tennis_cutoffs
from sharp_eyes.history.fetch import HistoryCache

HERE = Path(__file__).parent
FROZEN_AT = parse_ts("2026-10-29T14:10:00Z") or 0.0
UNIT = 5.0
DELAYS = (30, 120)
MAX_WAIT = 30 * 60
TRADES = HERE / "novig-trades"
OUT = HERE / "novig-tier2-bets.csv"


def norm(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return "".join(ch if ch.isalnum() else " " for ch in text).split()


def last(name: str) -> str:
    w = norm(name)
    return w[-1] if w else ""


def novig_day(day: date) -> Path | None:
    """ATP/WTA match-winner rows of one Novig trade file, downloaded once."""
    path = TRADES / f"{day}.csv.gz"
    if path.exists():
        return path
    url = f"https://data.novig.com/reporting/trade-data/{day}/trades.csv"
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "sharp-eyes"}), timeout=300).read()
    except Exception:
        return None  # not published yet
    TRADES.mkdir(exist_ok=True)
    rows = csv.DictReader(io.StringIO(raw.decode()))
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "outcomeId", "marketId", "price", "qty", "side"])
        for r in rows:
            if r["league"] in ("ATP", "WTA") and r["marketType"] == "MONEY" and r["tradeType"] == "STRAIGHT":
                ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).timestamp()
                w.writerow([round(ts, 3), r["outcomeId"], r["marketId"], round(float(r["cost"]) / float(r["qty"]), 4), r["qty"], r["side"]])
    tmp.replace(path)
    return path


def load_novig() -> tuple[list[dict], dict[str, list[tuple[float, float]]]]:
    """Listed match-winner markets (from all snapshots) and taker buys per outcome."""
    markets: dict[str, dict] = {}
    for snap in sorted((HERE / "novig-listings").glob("*.json")):
        body = json.loads(snap.read_text())
        for lg in body["leagues"].values():
            events = {e["eventId"]: e for e in lg["events"]}
            for m in lg["markets"]:
                if m.get("marketType") == "MONEY" and m["eventId"] in events:
                    e = events[m["eventId"]]
                    markets[m["marketId"]] = {"desc": e["description"], "start": (e.get("startsTs") or 0) / 1000,
                                              "outcomes": [(o["outcomeId"], o["name"]) for o in m["outcomes"]]}
    buys: dict[str, list[tuple[float, float]]] = defaultdict(list)
    day = date(2026, 10, 29)
    while day < datetime.now(UTC).date():
        path = novig_day(day)
        if path is not None:
            for r in csv.DictReader(gzip.open(path, "rt")):
                if r["side"] == "TAKER":
                    buys[r["outcomeId"]].append((float(r["ts"]), float(r["price"])))
        day += timedelta(days=1)
    for v in buys.values():
        v.sort()
    return list(markets.values()), buys


def find_outcome(nmarkets: list[dict], players: tuple[str, str], pick: str, start: float) -> str | None:
    la, lb = last(players[0]), last(players[1])
    lp = last(pick)
    for m in nmarkets:
        words = set(norm(m["desc"]))
        if la in words and lb in words and abs(m["start"] - start) <= 12 * 3600:
            for oid, name in m["outcomes"]:
                if lp in norm(name):
                    return oid
    return None


def main(data_dir: str) -> None:
    tier2 = {(r["wallet"], r["tour"]) for r in csv.DictReader(open(HERE / "tier2-list.csv"))}
    wallets = {w for w, _ in tier2}
    nmarkets, buys = load_novig()
    cache = HistoryCache(Path(data_dir))
    rows, matches, both = [], 0, 0
    for eid in cache.event_ids():
        ev = cache.load_event(eid)
        tour = ev.get("season")
        money = [m for m in ev["markets"] if m.get("sportsMarketType") == "moneyline"]
        if not money:
            continue
        mk = money[0]
        start = parse_ts(mk.get("gameStartTime")) or parse_ts(ev.get("startTime")) or 0
        if start < FROZEN_AT:
            continue
        matches += 1
        fills = sorted(cache.load_fills(eid), key=lambda f: f[0])
        paths = price_paths(fills)
        markets = tennis_cutoffs(parse_markets(ev), paths)
        info = markets.get(mk["conditionId"])
        if info is None:
            continue  # not settled
        first: dict[int, tuple[float, str, float]] = {}
        for ts, w, cid, oi, side, price, size, taker in fills:
            if cid != mk["conditionId"] or (w, tour) not in tier2 or ts >= info.kickoff:
                continue
            k = oi if side == "BUY" else 1 - oi
            if k not in first:
                first[k] = (ts, w, price if side == "BUY" else 1 - price)
        if not first:
            continue
        if len(first) == 2:
            both += 1
            continue
        (k, (ts, w, q)), = first.items()
        outcomes = json.loads(mk.get("outcomes") or "[]")
        title = ev["title"].rpartition(": ")[2]
        if " vs " not in title or len(outcomes) != 2:
            continue
        players = tuple(title.split(" vs ", 1))
        oid = find_outcome(nmarkets, players, outcomes[k], info.kickoff)
        payout = info.payout[k]
        row = {"match": ev["title"], "pick": outcomes[k], "wallet": w[:10], "placed_utc": datetime.fromtimestamp(ts, UTC).strftime("%m-%d %H:%M"),
               "sharp_price": round(q, 3), "result": "void" if payout == 0.5 else ("won" if payout == 1 else "lost"), "on_novig": int(oid is not None)}
        for d in DELAYS:
            p = None
            if oid:
                for t2, price in buys.get(oid, []):
                    if t2 >= ts + d:
                        if t2 < min(ts + d + MAX_WAIT, info.kickoff):
                            p = price
                        break
            row[f"novig_{d}s"] = "" if p is None else p
            row[f"novig_{d}s_pnl"] = "" if p is None or not 0 < p < 1 else round(UNIT / p * (payout - p), 2)
            pp = paths[mk["conditionId"]].price_after(ts + d, info.kickoff) if mk["conditionId"] in paths else None
            if pp is not None:
                pq = pp if k == 0 else 1 - pp
                fee = info.fee_rate * pq * (1 - pq)
                row[f"poly_{d}s"] = round(pq, 3)
                row[f"poly_{d}s_pnl"] = round(UNIT / pq * (payout - pq - fee), 2)
            else:
                row[f"poly_{d}s"] = row[f"poly_{d}s_pnl"] = ""
        rows.append(row)
    rows.sort(key=lambda r: r["placed_utc"])
    cols = ["match", "pick", "wallet", "placed_utc", "sharp_price", "result", "on_novig"]
    for d in DELAYS:
        cols += [f"novig_{d}s", f"novig_{d}s_pnl", f"poly_{d}s", f"poly_{d}s_pnl"]
    with open(OUT, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        wr.writerows(rows)
    print(f"Tier 2 on Novig: {matches} matches since freeze, {len(rows)} picks, {both} skipped (both sides), "
          f"{sum(r['on_novig'] for r in rows)} found on Novig")
    for venue in ("novig", "poly"):
        for d in DELAYS:
            bets = [r for r in rows if r[f"{venue}_{d}s_pnl"] != ""]
            won = sum(r["result"] == "won" for r in bets)
            lost = sum(r["result"] == "lost" for r in bets)
            voids = sum(r["result"] == "void" for r in bets)
            pnl = sum(r[f"{venue}_{d}s_pnl"] for r in bets)
            name = "Novig, no fee" if venue == "novig" else "Polymarket next trade, with fee"
            print(f"  {name}, {d}s: {len(bets)} bets {won}-{lost} +{voids} voids, ${pnl:+.2f} ({pnl / (UNIT * len(bets)) if bets else 0:+.1%})")


if __name__ == "__main__":
    main(sys.argv[1])
