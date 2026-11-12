"""Pooled after-period numbers for wallet-markets classified on the before-period.
Usage: pooled.py SIGNALS.csv.gz BEFORE_WALLET_MARKETS.csv SPLIT_DATE OUT.csv"""
import sys
from datetime import datetime, timezone
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from classify import clustered, H

sig, before, split, out = sys.argv[1:5]
cut = datetime.fromisoformat(split).replace(tzinfo=timezone.utc).timestamp()
s = pd.read_csv(sig, dtype={"eid": str})
s = s[s.ts >= cut]
s["seg"] = s.tour + " | " + np.where(s.phase == "pre", "pre-match", "in-play") + " | " + s.kind
b = pd.read_csv(before)[["wallet", "seg", "class", "tier"]]
b = b[~b.seg.str.contains("completed_match")]
s = s.merge(b, on=["wallet", "seg"])
for d in H:
    c = s[f"c{d}"]
    s[f"cev{d}"] = (s.pay - c - 0.05 * c * (1 - c)) / c
    s[f"cnf{d}"] = (s.pay - c) / c
    s[f"mk{d}"] = s.mid0 + s.m120 - c - 0.05 * c * (1 - c)  # per share: mid 2 min after the signal minus copy cost
s["own"] = (s.pay - s.q) / s.q
cols = ["own", "m5", "m30", "m60", "m120"] + [f"mk{d}" for d in H] + [f"cev{d}" for d in H] + [f"cnf{d}" for d in H]
r = clustered(s, ["class", "phase"], cols)
r.to_csv(out)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
show = ["own"] + [f"m{h}" for h in (5, 30, 120)] + [f"mk{d}" for d in (5, 30, 120)] + [f"cev{d}" for d in H] + ["cnf30"]
print(r[show + ["cev5_t", "cev30_t", "cev120_t", "cev30_n"]].round(4).to_string())
