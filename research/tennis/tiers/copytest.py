"""Copy test: follow tiered wallet-markets (picked before SPLIT) on bets after SPLIT.
Each bet's first fill is copied at the next printed price DELAY seconds later, 1 share,
paying today's taker fee 0.05*q*(1-q). Same phase only (pre-match copies must land before start).
Usage: copy.py DATA_DIR TIERS.csv SPLIT_DATE OUT.csv"""
import csv, sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path
from sharp_eyes.history.analyze import parse_markets, price_paths, tennis_cutoffs
from sharp_eyes.history.fetch import HistoryCache

DATA = Path(sys.argv[1])
SPLIT = datetime.fromisoformat(sys.argv[3]).replace(tzinfo=timezone.utc).timestamp()
FEE = 0.05
DELAYS = (30, 120)
T = {}
for r in csv.DictReader(open(sys.argv[2])):
    if r["tier"] in ("Tier 1", "Tier 2"):
        T[(r["wallet"], r["market"])] = (r["tier"], float(r["taker_share"]))
WALLETS = {w for w, _ in T}


def one(eid):
    c = HistoryCache(DATA)
    try:
        ev = c.load_event(eid)
    except Exception:
        return []
    if not ev.get("startTime") or ev["startTime"] < sys.argv[3]:
        pass  # filter by fill time below
    fills = sorted(c.load_fills(eid), key=lambda f: f[0])
    if not fills or fills[-1][0] < SPLIT:
        return []
    markets = tennis_cutoffs(parse_markets(ev), price_paths(fills))
    paths = price_paths(fills, 0.0, 1.0)
    smt = {m["conditionId"]: m.get("sportsMarketType") or "?" for m in ev["markets"]}
    seen, out = set(), []
    for ts, w, cid, oi, side, price, size, taker in fills:
        if w not in WALLETS or ts < SPLIT:
            continue
        m = markets.get(cid)
        if m is None or not 0.03 <= price <= 0.97 or (m.closed_at and ts >= m.closed_at):
            continue
        pre = ts < m.kickoff
        mk = f"{ev['season']} | {'pre-match' if pre else 'in-play'} | {smt.get(cid, '?')}"
        if (w, mk) not in T:
            continue
        k = oi if side == "BUY" else 1 - oi
        key = (w, cid, pre, k)
        if key in seen:
            continue
        seen.add(key)
        q = price if side == "BUY" else 1 - price
        row = {"wallet": w, "market": mk, "tier": T[(w, mk)][0], "maker": int(T[(w, mk)][1] < 0.5),
               "eid": eid, "ts": ts, "q": q, "own_pnl": m.payout[k] - q}
        end = m.kickoff if pre else (m.closed_at or float("inf"))
        for d in DELAYS:
            p = paths[cid].price_after(ts + d, end) if cid in paths else None
            cq = None if p is None else (p if k == 0 else 1 - p)
            if cq is None or not 0.03 <= cq <= 0.97:
                row[f"c{d}"] = ""
            else:
                row[f"c{d}"] = round(m.payout[k] - cq - FEE * cq * (1 - cq), 5)
                row[f"q{d}"] = round(cq, 4)
        out.append(row)
    return out


if __name__ == "__main__":
    ids = HistoryCache(DATA).event_ids()
    cols = ["wallet", "market", "tier", "maker", "eid", "ts", "q", "own_pnl", "c30", "q30", "c120", "q120"]
    with open(sys.argv[4], "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols, restval="")
        wr.writeheader()
        with Pool(4) as p:
            for rows in p.imap_unordered(one, ids, chunksize=20):
                wr.writerows(rows)
