"""Trade-tape mid vs real order-book mid, and copy at the real best ask, Oct 27 - Nov 6.
Usage: book_compare.py BOOK_SIGNALS.csv.gz BEFORE_WALLET_MARKETS.csv OUT.csv"""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from classify import clustered, H

s = pd.read_csv(sys.argv[1], dtype={"eid": str})
s = s[s.bmid0.notna()].copy()
s["seg"] = s.tour + " | " + np.where(s.phase == "pre", "pre-match", "in-play") + " | " + s.kind
for h in H:
    s.loc[s[f"m{h}"].isna(), f"bm{h}"] = np.nan  # same phase cut as the tape
print("signals with a book:", len(s))
print("tape vs book mid at signal, median abs diff:", (s.mid0 - s.bmid0).abs().median().round(4),
      " corr of 60 s move:", s[["m60", "bm60"]].corr().iloc[0, 1].round(3))
print("median book spread (pre / live):", s.groupby("phase").bspr0.median().to_dict())
b = pd.read_csv(sys.argv[2])[["wallet", "seg", "class"]]
s = s.merge(b, on=["wallet", "seg"], how="left")
s["class"] = s["class"].fillna("not classified")
for d in H:
    a = s[f"ba{d}"]
    s[f"bev{d}"] = (s.pay - a - 0.05 * a * (1 - a)) / a  # copy at the real best ask, intl fee
    s[f"bnf{d}"] = (s.pay - a) / a
    c = s[f"c{d}"]
    s[f"cev{d}"] = (s.pay - c - 0.05 * c * (1 - c)) / c
cols = ["m5", "bm5", "m30", "bm30", "m120", "bm120", "pre60", "bpre60"] + [f"cev{d}" for d in (5, 30, 120)] \
    + [f"bev{d}" for d in H] + ["bnf30"]
r = clustered(s, ["class", "phase"], cols)
r.to_csv(sys.argv[3])
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
print(r[cols + ["bev5_t", "bev30_t", "bev30_n"]].round(4).to_string())
