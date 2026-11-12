"""Re-measure signals with the real order book (PendulumFlow best bid / ask).
For each signal inside the archive window, in the signal's own outcome token:
  bmid0  book mid at the signal second;  bspr0  spread then
  bpre60 bmid0 minus the mid 60 s earlier
  bm{h}  mid at ts+h minus bmid0
  ba{d}  best ask at ts+d (top of book; what a follower lifting the ask pays for the first shares)
Archive clock vs Data API second: OFFSET seconds are added to the signal time.
Usage: book_signals.py SIGNALS.csv.gz TOKENS.json BOOK_DIR OFFSET OUT.csv.gz"""
import glob, json, os, sys
from datetime import datetime, timezone
import duckdb
import numpy as np
import pandas as pd

H = (5, 15, 30, 60, 120)
sig_path, tok_path, book_dir, offset, out = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5]
files = sorted(glob.glob(f"{book_dir}/*.parquet"))
hours = {os.path.basename(f)[:13]: f for f in files}
t_lo = datetime.fromisoformat(min(hours) + ":00:00+00:00").timestamp()
t_hi = datetime.fromisoformat(max(hours) + ":00:00+00:00").timestamp() + 3600
s = pd.read_csv(sig_path, dtype={"eid": str})
s = s[(s.ts >= t_lo + 120) & (s.ts < t_hi - 1800)].copy()
tok = json.load(open(tok_path))
s["asset"] = [("%064X" % int(tok[c][k])) if c in tok else None for c, k in zip(s.cid, s.k)]
s = s[s.asset.notna()]
s["hour"] = pd.to_datetime(s.ts, unit="s", utc=True).dt.strftime("%Y-%m-%dT%H")
con = duckdb.connect()
res = []
for hr, g in s.groupby("hour"):
    t0 = datetime.fromisoformat(hr + ":00:00+00:00").timestamp()
    need = [hours.get(datetime.fromtimestamp(t0 + d * 3600, timezone.utc).strftime("%Y-%m-%dT%H")) for d in (-1, 0, 1)]
    need = [f for f in need if f]
    assets = ",".join(f"'{a}'" for a in g.asset.unique())
    b = con.sql(f"SELECT asset, t_us, bid, ask FROM read_parquet({need}) WHERE asset IN ({assets}) ORDER BY asset, t_us").df()
    by = {a: (d.t_us.to_numpy() / 1e6, d.bid.to_numpy(), d.ask.to_numpy()) for a, d in b.groupby("asset")}
    for r in g.itertuples():
        x = by.get(r.asset)
        row = {"idx": r.Index}
        if x is None:
            res.append(row); continue
        t, bid, ask = x

        def at(sec):
            i = np.searchsorted(t, sec + offset, side="right") - 1
            if i < 0 or not (bid[i] > 0 and ask[i] < 1 and ask[i] >= bid[i]):
                return None, None, None
            return (bid[i] + ask[i]) / 2, ask[i], ask[i] - bid[i]

        m0, _, sp = at(r.ts)
        if m0 is None:
            res.append(row); continue
        row["bmid0"], row["bspr0"] = round(m0, 4), round(sp, 4)
        mb, _, _ = at(r.ts - 60)
        row["bpre60"] = None if mb is None else round(m0 - mb, 4)
        for h in H:
            mh, ah, _ = at(r.ts + h)
            row[f"bm{h}"] = None if mh is None else round(mh - m0, 4)
            row[f"ba{h}"] = ah
        res.append(row)
    print(hr, len(g), flush=True)
r = pd.DataFrame(res).set_index("idx")
s = s.join(r)
s.to_csv(out, index=False, compression="gzip")
