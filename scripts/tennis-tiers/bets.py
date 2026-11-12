"""One row per bet = (wallet, market, phase) net position, from the tennis history cache.
Usage: bets.py DATA_DIR OUT.csv.gz"""
import csv, gzip, sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path
from sharp_eyes.history.analyze import (PRICE_CAP, PRICE_FLOOR, MARK_HORIZON, parse_markets,
                                        price_paths, tennis_cutoffs)
from sharp_eyes.history.fetch import HistoryCache

DATA = Path(sys.argv[1])
COLS = ["wallet", "eid", "tour", "tourn", "kind", "phase", "ts", "stake", "taker_stake", "pnl",
        "fee", "clv_p", "clv_s", "mk_p", "mk_s"]


def one(eid):
    c = HistoryCache(DATA)
    try:
        event = c.load_event(eid)
        fills = sorted(c.load_fills(eid), key=lambda f: f[0])
    except Exception:
        return []
    markets = parse_markets(event)
    paths = price_paths(fills)
    markets = tennis_cutoffs(markets, paths)
    marks = price_paths(fills, 0.0, 1.0)
    closes = {cid: paths[cid].close(m.kickoff) if cid in paths else None for cid, m in markets.items()}
    title = event.get("title") or ""
    tourn = title.split(":")[0].replace(", Qualification", "").strip()
    smt = {mm["conditionId"]: (mm.get("sportsMarketType") or "?") for mm in event["markets"]}
    acc = {}
    for ts, w, cid, oi, side, price, size, taker in fills:
        m = markets.get(cid)
        if m is None or not w or not PRICE_FLOOR <= price <= PRICE_CAP:
            continue
        if m.closed_at is not None and ts >= m.closed_at:
            continue
        k = oi if side == "BUY" else 1 - oi
        q = price if side == "BUY" else 1 - price
        stake = size * q
        fee = m.fee_rate * size * (price * (1 - price)) ** m.fee_exponent if taker else 0.0
        pre = ts < m.kickoff
        key = (w, cid, "pre" if pre else "live")
        a = acc.get(key)
        if a is None:
            a = acc[key] = [ts, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        a[1] += stake
        a[2] += stake if taker else 0.0
        a[3] += size * (m.payout[k] - q) - fee
        a[4] += fee
        if pre:
            c0 = closes.get(cid)
            if c0 is not None:
                ck = c0 if k == 0 else 1 - c0
                a[5] += size * (ck - q)
                a[6] += stake
        elif taker and cid in marks:
            end = m.closed_at if m.closed_at is not None else float("inf")
            later = marks[cid].price_after(ts + MARK_HORIZON, end)
            if later is not None:
                a[7] += size * ((later if k == 0 else 1 - later) - q)
                a[8] += stake
    out = []
    for (w, cid, ph), a in acc.items():
        out.append([w, eid, event.get("season"), tourn, smt.get(cid, "?"), ph, int(a[0])]
                   + [round(x, 4) for x in a[1:]])
    return out


if __name__ == "__main__":
    ids = HistoryCache(DATA).event_ids()
    with gzip.open(sys.argv[2], "wt", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(COLS)
        n = 0
        with Pool(4) as p:
            for rows in p.imap_unordered(one, ids, chunksize=20):
                wr.writerows(rows)
                n += 1
                if n % 1000 == 0:
                    print(n, flush=True)
