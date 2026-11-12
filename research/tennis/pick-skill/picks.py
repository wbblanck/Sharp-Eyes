"""One row per (wallet, market, side) pre-match pick: first buy time, price paid,
price for sale 30 s later (next print, same rule as paper test), payout.
Usage: picks.py DATA_DIR OUT.csv"""
import csv, sys
from multiprocessing import Pool
from pathlib import Path
from sharp_eyes.history.analyze import parse_markets, parse_ts, price_paths, tennis_cutoffs
from sharp_eyes.history.fetch import HistoryCache
DATA = Path(sys.argv[1])

def one(eid):
    c = HistoryCache(DATA); out = []
    try:
        event = c.load_event(eid); fills = sorted(c.load_fills(eid), key=lambda f: f[0])
    except Exception:
        return out
    paths = price_paths(fills)
    markets = tennis_cutoffs(parse_markets(event), paths)
    seen = {}
    for ts, w, cid, oi, side, price, size, tk in fills:
        m = markets.get(cid)
        if m is None or ts >= m.kickoff or m.payout is None:
            continue
        k = oi if side == "BUY" else 1 - oi
        q = price if side == "BUY" else 1 - price
        key = (w, cid, k)
        if key in seen:
            seen[key][3] += size * q
            continue
        seen[key] = [ts, q, m, size * q]
    for (w, cid, k), (ts, q, m, usd) in seen.items():
        p30 = paths[cid].price_after(ts + 30, m.kickoff) if cid in paths else None
        q30 = None if p30 is None else (p30 if k == 0 else 1 - p30)
        out.append({"wallet": w, "eid": eid, "cid": cid, "kind": m.kind, "k": k, "ts": round(ts),
                    "q": round(q, 4), "q30": "" if q30 is None else round(q30, 4),
                    "payout": m.payout[k], "usd": round(usd, 2)})
    return out

if __name__ == "__main__":
    ids = HistoryCache(DATA).event_ids()
    with open(sys.argv[2], "w", newline="") as fh:
        w = None
        with Pool(4) as p:
            for rows in p.imap_unordered(one, ids, chunksize=20):
                for r in rows:
                    if w is None:
                        w = csv.DictWriter(fh, fieldnames=list(r)); w.writeheader()
                    w.writerow(r)
