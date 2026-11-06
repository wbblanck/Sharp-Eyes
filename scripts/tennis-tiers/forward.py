"""Forward test: tiers assigned on data before SPLIT, measured after SPLIT in the same market.
Usage: forward.py BETS.csv.gz TIERS_BEFORE.csv SPLIT_DATE"""
import math, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd

b = pd.read_csv(sys.argv[1], dtype={"eid": str})
t = pd.read_csv(sys.argv[2])
split = datetime.fromisoformat(sys.argv[3]).replace(tzinfo=timezone.utc).timestamp()
b = b[(b.ts >= split) & (b.stake > 0)]
b["market"] = b.tour + " | " + np.where(b.phase == "pre", "pre-match", "in-play") + " | " + b.kind
b["edge_p"] = np.where(b.phase == "pre", b.clv_p, b.mk_p)
b["edge_s"] = np.where(b.phase == "pre", b.clv_s, b.mk_s)
t["tier"] = t.tier.fillna("untiered (100+ bets)")
m = b.merge(t[["wallet", "market", "tier"]], on=["wallet", "market"], how="left")
m["tier"] = m.tier.fillna("everyone else")

def ratio_t(x, y):
    sy = y.sum()
    if sy <= 0 or len(x) < 2: return np.nan, np.nan
    r = x.sum() / sy
    var = len(x) / (len(x) - 1) * ((x - r * y) ** 2).sum() / sy ** 2
    return r, (r / math.sqrt(var) if var > 0 else np.nan)

out = []
for (tier, phase), d in m.groupby(["tier", "phase"]):
    ev = d.groupby("eid")[["pnl", "stake", "edge_p", "edge_s", "fee"]].sum()
    roi, rt = ratio_t(ev.pnl.values, ev.stake.values)
    es = ev[ev.edge_s > 0]
    e, et = ratio_t(es.edge_p.values, es.edge_s.values)
    out.append(dict(tier=tier, phase=phase, wallets=d.wallet.nunique(), bets=len(d), stake=round(d.stake.sum()),
                    roi=round(roi, 4), roi_t=round(rt, 2), edge=round(e, 4), edge_t=round(et, 2),
                    fee=round(d.fee.sum() / d.stake.sum(), 4)))
print(pd.DataFrame(out).to_string())
# per tiered wallet-market
pw = []
for (w, mk, tier), d in m[m.tier.str.startswith("Tier")].groupby(["wallet", "market", "tier"]):
    ev = d.groupby("eid")[["pnl", "stake"]].sum()
    roi, rt = ratio_t(ev.pnl.values, ev.stake.values)
    pw.append(dict(wallet=w, market=mk, tier=tier, bets_after=len(d), roi_after=roi, roi_t_after=rt))
pw = pd.DataFrame(pw)
if len(pw):
    print(pw.groupby("tier").agg(active=("wallet", "size"), positive=("roi_after", lambda s: (s > 0).sum()),
                                 t_over_2=("roi_t_after", lambda s: (s > 2).sum())))
    pw.to_csv(sys.argv[2].replace(".csv", "-forward.csv"), index=False, float_format="%.4f")
