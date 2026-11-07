"""One row per signal = the first fill of each new position a wallet opens
(wallet, market, phase, outcome), from the tennis history cache, with the
market's mid-price path around it.

Mid proxy (no historical order books for the full year): the last price a taker
paid to BUY outcome 0 (= ask) and the last price a taker SOLD outcome 0 at
(= bid), averaged. Falls back to the last print when one side is missing,
older than MID_STALE seconds, or the two are crossed / wider than MID_WIDE.

Columns, all prices in the signal's own outcome (k) terms:
  q        price the wallet paid on that first fill
  mid0     mid from prints strictly before the signal second
  pre60    mid0 minus the mid 60 s earlier (did the price already move their way?)
  m{h}     mid at ts+h minus mid0, h in HORIZONS
  c{d}     price of the first taker BUY of outcome k printed at or after ts+d
           (what a follower lifting the ask would pay), blank if none before end
Usage: signals.py DATA_DIR OUT.csv.gz"""
import bisect, csv, gzip, sys
from multiprocessing import Pool
from pathlib import Path
from sharp_eyes.history.analyze import parse_markets, price_paths, tennis_cutoffs
from sharp_eyes.history.fetch import HistoryCache

DATA = Path(sys.argv[1])
HORIZONS = (5, 15, 30, 60, 120)
MID_STALE = 600
MID_WIDE = 0.10
COPY_WAIT = 1800
COLS = (["wallet", "eid", "cid", "tour", "kind", "phase", "ts", "k", "taker", "usd", "q", "pay",
         "fee_rate", "mid0", "pre60"] + [f"m{h}" for h in HORIZONS] + [f"c{h}" for h in HORIZONS])


class Book:
    """Taker prints of one market in outcome-0 terms."""

    def __init__(self):
        self.ts, self.mid, self.ask_ts, self.ask_p, self.bid_ts, self.bid_p = [], [], [], [], [], []
        self.a = self.b = None  # (ts, price)

    def add(self, ts, p0, up):
        if up:
            self.a = (ts, p0)
            self.ask_ts.append(ts); self.ask_p.append(p0)
        else:
            self.b = (ts, p0)
            self.bid_ts.append(ts); self.bid_p.append(p0)
        a, b = self.a, self.b
        m = p0
        if a and b and ts - a[0] <= MID_STALE and ts - b[0] <= MID_STALE and 0 <= a[1] - b[1] <= MID_WIDE:
            m = (a[1] + b[1]) / 2
        if self.ts and self.ts[-1] == ts:
            self.mid[-1] = m  # keep the last state within a second
        else:
            self.ts.append(ts); self.mid.append(m)

    def mid_at(self, t, strict=False):
        """Mid after all prints at or before t (strictly before when strict)."""
        i = (bisect.bisect_left if strict else bisect.bisect_right)(self.ts, t) - 1
        return self.mid[i] if i >= 0 else None

    def next_buy(self, k, t, end):
        """First print at/after t where a taker bought outcome k: its price in k terms."""
        ts, ps = (self.ask_ts, self.ask_p) if k == 0 else (self.bid_ts, self.bid_p)
        i = bisect.bisect_left(ts, t)
        if i < len(ts) and ts[i] < end and ts[i] <= t + COPY_WAIT:
            return ps[i] if k == 0 else 1 - ps[i]
        return None


def r4(x):
    return "" if x is None else round(x, 4)


def one(eid):
    c = HistoryCache(DATA)
    try:
        ev = c.load_event(eid)
        fills = sorted(c.load_fills(eid), key=lambda f: f[0])
    except Exception:
        return []
    markets = tennis_cutoffs(parse_markets(ev), price_paths(fills))
    smt = {m["conditionId"]: m.get("sportsMarketType") or "?" for m in ev["markets"]}
    books = {}
    for ts, w, cid, oi, side, price, size, taker in fills:
        if taker and 0.0 < price < 1.0 and cid in markets:
            up = (side == "BUY") == (oi == 0)
            books.setdefault(cid, Book()).add(ts, price if oi == 0 else 1 - price, up)
    seen, out = set(), []
    for ts, w, cid, oi, side, price, size, taker in fills:
        m = markets.get(cid)
        bk = books.get(cid)
        if m is None or bk is None or not w or not 0.03 <= price <= 0.97:
            continue
        if m.closed_at and ts >= m.closed_at:
            continue
        pre = ts < m.kickoff
        k = oi if side == "BUY" else 1 - oi
        key = (w, cid, pre, k)
        if key in seen:
            continue
        seen.add(key)
        q = price if side == "BUY" else 1 - price
        end = m.kickoff if pre else (m.closed_at or float("inf"))
        sgn = 1 if k == 0 else -1
        m0 = bk.mid_at(ts, strict=True)
        if m0 is None:
            continue
        mb = bk.mid_at(ts - 60)
        row = [w, eid, cid, ev.get("season"), smt.get(cid, "?"), "pre" if pre else "live", ts, k, taker,
               round(size * q, 2), round(q, 4), m.payout[k], m.fee_rate,
               round(m0 if k == 0 else 1 - m0, 4), r4(None if mb is None else sgn * (m0 - mb))]
        for h in HORIZONS:
            mh = bk.mid_at(ts + h) if ts + h < end else None
            row.append(r4(None if mh is None else sgn * (mh - m0)))
        for d in HORIZONS:
            row.append(r4(bk.next_buy(k, ts + d, end)))
        out.append(row)
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
