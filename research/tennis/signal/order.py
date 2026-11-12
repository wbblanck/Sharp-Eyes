"""Do some sharp wallets enter before the other sharp wallets, and does that help a copier?
Sharp set = wallet-markets that were information leaders or Tier 1/2 on data before SPLIT
(from classify.py --before and the tier forward-test file). Measured on signals after SPLIT.
For each sharp signal, other sharp wallets' signals on the same market and side within WIN s:
  first   no other sharp entered in the WIN s before it
  joined  at least one other sharp entered in the WIN s after it
  second  it is the second distinct sharp wallet in WIN s (the "confirmation" moment)
Usage: order.py SIGNALS.csv.gz BEFORE_WALLET_MARKETS.csv TIERS_BEFORE.csv SPLIT OUT_DIR"""
import sys
from datetime import datetime, timezone
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from classify import clustered, H

sig, cls, tiers, split, outdir = sys.argv[1:6]
WIN = 120
cut = datetime.fromisoformat(split).replace(tzinfo=timezone.utc).timestamp()
c = pd.read_csv(cls)[["wallet", "seg", "class"]]
t = pd.read_csv(tiers).rename(columns={"market": "seg"})[["wallet", "seg", "tier"]]
sh = c.merge(t, on=["wallet", "seg"], how="outer")
sh = sh[(sh["class"] == "information leader") | sh.tier.isin(["Tier 1", "Tier 2"])]
sh = sh[~sh.seg.str.contains("completed_match")]
sh["group"] = np.where(sh["class"] == "information leader", "leader", "tier1/2 not leader")
s = pd.read_csv(sig, dtype={"eid": str})
s = s[s.ts >= cut]
s["seg"] = s.tour + " | " + np.where(s.phase == "pre", "pre-match", "in-play") + " | " + s.kind
s = s.merge(sh[["wallet", "seg", "group"]], on=["wallet", "seg"])
s = s.sort_values(["cid", "phase", "k", "ts"]).reset_index(drop=True)
first, joined, second, lead = [], [], [], []
for _, g in s.groupby(["cid", "phase", "k"], sort=False):
    ts, w = g.ts.to_numpy(), g.wallet.to_numpy()
    for i in range(len(g)):
        lo = np.searchsorted(ts, ts[i] - WIN, "left")
        hi = np.searchsorted(ts, ts[i] + WIN, "right")
        before = {x for x in w[lo:i] if x != w[i]}
        after = [j for j in range(i + 1, hi) if w[j] != w[i]]
        first.append(not before)
        joined.append(bool(after))
        second.append(len(before) == 1 and len(set(w[lo:i + 1])) == 2)
        lead.append(ts[after[0]] - ts[i] if after and not before else np.nan)
s["first"], s["joined"], s["second"], s["lead"] = first, joined, second, lead
for d in H:
    cc = s[f"c{d}"]
    s[f"cev{d}"] = (s.pay - cc - 0.05 * cc * (1 - cc)) / cc
s["role"] = np.select([s["first"] & s.joined, s["first"] & ~s.joined, s.second],
                      ["first, others followed", "alone", "second sharp in"], "later")
cols = ["m5", "m30", "m120", "pre60"] + [f"cev{d}" for d in H]
r = clustered(s, ["phase", "role"], cols)
r.to_csv(f"{outdir}/order-by-role.csv")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
print(r[cols + ["cev5_t", "cev30_t", "cev30_n"]].round(4).to_string())
# per wallet-market: how often first when another sharp is around
x = s[s.joined | ~s["first"]]
w = x.groupby(["wallet", "seg", "group"]).agg(contested=("first", "size"), first_rate=("first", "mean"),
                                              med_lead=("lead", "median")).reset_index()
w = w[w.contested >= 50].sort_values("first_rate", ascending=False)
w.to_csv(f"{outdir}/order-by-wallet.csv", index=False)
print(len(w), "wallet-markets with 50+ contested signals; first-rate quartiles", w.first_rate.quantile([.1, .5, .9]).round(2).to_dict())
print(w.head(12).round(3).to_string(index=False))
s[["wallet", "seg", "group", "cid", "phase", "k", "ts", "role"]].to_csv(f"{outdir}/order-signals.csv.gz", index=False)
