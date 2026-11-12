"""Archive clock minus Data API trade second: match Data API taker fills to the
archive's last_trade_price prints by token, price and size (within 30 s).
Usage: offset.py DATA_DIR TOKENS.json BOOK_DIR"""
import glob, json, sys
from collections import defaultdict
import duckdb, numpy as np
from sharp_eyes.history.fetch import HistoryCache

c = HistoryCache(__import__("pathlib").Path(sys.argv[1]))
tok = json.load(open(sys.argv[2]))
files = sorted(glob.glob(f"{sys.argv[3]}/*.trades"))
tr = duckdb.sql(f"SELECT asset, t_us/1e6 t, price, size FROM read_parquet({files})").df()
lo, hi = tr.t.min(), tr.t.max()
idx = defaultdict(list)
for a, t, p, z in tr.itertuples(index=False):
    idx[(a, round(p, 4), round(z, 2))].append(t)
d = []
for eid in c.event_ids():
    try:
        fills = c.load_fills(eid)
    except Exception:
        continue
    if not fills or fills[0][0] > hi or max(f[0] for f in fills) < lo:
        continue
    for ts, w, cid, oi, side, price, size, taker in fills:
        if not taker or cid not in tok:
            continue
        a = "%064X" % int(tok[cid][oi])
        for t in idx.get((a, round(price, 4), round(size, 2)), ()):
            if abs(t - ts) < 30:
                d.append(t - ts)
d = np.array(d)
print("matches", len(d))
for q in (5, 25, 50, 75, 95):
    print(q, round(float(np.percentile(d, q)), 2))
