"""Tier wallets per tennis market from bets.csv.gz.
Usage: tiers.py BETS.csv.gz OUTDIR [--before YYYY-MM-DD] [--after YYYY-MM-DD]"""
import math, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd

src, outdir = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
def opt(name):
    return datetime.fromisoformat(args[args.index(name) + 1]).replace(tzinfo=timezone.utc).timestamp() if name in args else None
before, after = opt("--before"), opt("--after")

b = pd.read_csv(src, dtype={"eid": str})
if before: b = b[b.ts < before]
if after: b = b[b.ts >= after]
b = b[b.stake > 0]
b["seg"] = b.tour + " | " + np.where(b.phase == "pre", "pre-match", "in-play") + " | " + b.kind
# market edge: CLV vs close (pre-match), 5-min markout (in-play)
b["edge_p"] = np.where(b.phase == "pre", b.clv_p, b.mk_p)
b["edge_s"] = np.where(b.phase == "pre", b.clv_s, b.mk_s)
b["month"] = pd.to_datetime(b.ts, unit="s").dt.to_period("M")

def ratio_t(x, y):
    sy = y.sum()
    if sy <= 0 or len(x) < 2: return np.nan, np.nan
    r = x.sum() / sy
    var = len(x) / (len(x) - 1) * ((x - r * y) ** 2).sum() / sy ** 2
    return r, (r / math.sqrt(var) if var > 0 else np.nan)

def p_one(t):
    return 1.0 if t != t else 0.5 * math.erfc(t / math.sqrt(2))

counts = b.groupby(["wallet", "seg"]).size()
keep = counts[counts >= 100].index
g = b.set_index(["wallet", "seg"]).loc[keep].reset_index()
rows = []
for (w, seg), d in g.groupby(["wallet", "seg"], sort=False):
    d = d.sort_values("ts")
    ev = d.groupby("eid")[["pnl", "stake", "edge_p", "edge_s", "fee"]].sum()
    roi, roi_t = ratio_t(ev.pnl.values, ev.stake.values)
    es = ev[ev.edge_s > 0]
    edge, edge_t = ratio_t(es.edge_p.values, es.edge_s.values)
    fee_rate = d.fee.sum() / d.stake.sum()
    n3 = len(d)
    cuts = [0, n3 // 3, 2 * n3 // 3, n3]
    thirds = [d.pnl.iloc[cuts[i]:cuts[i+1]].sum() / d.stake.iloc[cuts[i]:cuts[i+1]].sum() for i in range(3)]
    by_t = d.groupby("tourn")[["pnl", "stake"]].sum()
    bt = by_t.pnl.idxmax()
    rest_t = by_t.drop(bt)
    roi_wo_t = rest_t.pnl.sum() / rest_t.stake.sum() if rest_t.stake.sum() > 0 else np.nan
    by_m = d.groupby("month")[["pnl", "stake"]].sum()
    bm = by_m.pnl.idxmax()
    rest_m = by_m.drop(bm)
    roi_wo_m = rest_m.pnl.sum() / rest_m.stake.sum() if rest_m.stake.sum() > 0 else np.nan
    rows.append(dict(
        wallet=w, market=seg, bets=len(d), won=int((d.pnl > 0).sum()), lost=int((d.pnl < 0).sum()),
        matches=len(ev), stake=round(d.stake.sum()), pnl=round(d.pnl.sum()), roi=roi, roi_t=roi_t,
        p_value=p_one(roi_t), edge=edge, edge_t=edge_t, fee_per_dollar=fee_rate,
        est_ev=(edge - fee_rate) if edge == edge else np.nan,
        taker_share=d.taker_stake.sum() / d.stake.sum(),
        roi_third1=thirds[0], roi_third2=thirds[1], roi_third3=thirds[2],
        best_tourn=bt, best_tourn_pnl=round(by_t.pnl.max()), roi_wo_best_tourn=roi_wo_t,
        best_month=str(bm), roi_wo_best_month=roi_wo_m,
        first=pd.to_datetime(d.ts.min(), unit="s").date(), last=pd.to_datetime(d.ts.max(), unit="s").date(),
    ))
r = pd.DataFrame(rows)

def tier(x):
    pos3 = sum(v > 0 for v in (x.roi_third1, x.roi_third2, x.roi_third3))
    if (x.bets >= 500 and x.roi > 0 and x.edge > 0 and x.p_value < 0.05 and pos3 == 3
            and x.roi_wo_best_tourn > 0 and x.roi_wo_best_month > 0):
        return "Tier 1"
    if x.bets >= 300 and x.edge > 0 and x.est_ev > 0 and x.roi > 0 and x.p_value < 0.10 and pos3 >= 2:
        return "Tier 2"
    if 100 <= x.bets < 300 and x.roi > 0 and x.edge > 0 and x.est_ev > 0:
        return "Tier 3"
    return ""
r["tier"] = r.apply(tier, axis=1)
r = r.sort_values(["tier", "market", "roi_t"], ascending=[True, True, False])
r.to_csv(f"{outdir}/wallet-markets.csv", index=False, float_format="%.4f")
seg = b.groupby("seg").agg(bets=("pnl", "size"), wallets=("wallet", "nunique"), stake=("stake", "sum"))
elig = r.groupby("market").agg(w100=("bets", lambda s: (s >= 100).sum()), w300=("bets", lambda s: (s >= 300).sum()),
                               w500=("bets", lambda s: (s >= 500).sum()))
tiers = r[r.tier != ""].groupby(["market", "tier"]).size().unstack(fill_value=0)
summary = seg.join(elig).join(tiers).fillna(0).sort_values("stake", ascending=False)
summary.to_csv(f"{outdir}/markets-summary.csv", float_format="%.0f")
print(summary.to_string())
print("tested wallet-markets:", len(r), "n>=300:", (r.bets >= 300).sum())
print(r[r.tier != ""].tier.value_counts())
