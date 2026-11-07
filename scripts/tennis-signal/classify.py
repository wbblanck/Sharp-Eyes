"""Score each wallet-market on what the price does around its trades, and sort
it into information leader / price follower / liquidity-dependent / unclear.
Usage: classify.py SIGNALS.csv.gz TIERS.csv OUT_DIR [--before YYYY-MM-DD | --after YYYY-MM-DD]"""
import sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd

H = (5, 15, 30, 60, 120)
MIN_SIGNALS = 100
T_SIG = 3.0  # thousands of wallet-markets are tested; t >= 3 keeps chance hits to a handful


def load(path, args):
    s = pd.read_csv(path, dtype={"eid": str})
    for flag, keep in (("--before", lambda ts, c: ts < c), ("--after", lambda ts, c: ts >= c)):
        if flag in args:
            cut = datetime.fromisoformat(args[args.index(flag) + 1]).replace(tzinfo=timezone.utc).timestamp()
            s = s[keep(s.ts, cut)]
    s["seg"] = s.tour + " | " + np.where(s.phase == "pre", "pre-match", "in-play") + " | " + s.kind
    s["edge"] = s.mid0 - s.q  # >0: got a better price than the mid
    s["roi"] = (s.pay - s.q) / s.q  # settlement return on the first fill, before fees
    for d in H:
        c = s[f"c{d}"]
        s[f"cev{d}"] = (s.pay - c - 0.05 * c * (1 - c)) / c  # copy at the ask, intl taker fee
        s[f"cnf{d}"] = (s.pay - c) / c  # no fee (Novig pre-match)
        s[f"drift{d}"] = s.m120 - s[f"m{d}"]  # price move still to come after a copier at d
    # control for the market's own recent move: residual of m60 on pre60 within phase x kind x taker
    s["res60"] = np.nan
    ok = s.pre60.notna() & s.m60.notna()
    for _, g in s[ok].groupby(["phase", "kind", "taker"]):
        if len(g) < 50:
            continue
        b = np.polyfit(g.pre60, g.m60, 1)
        s.loc[g.index, "res60"] = g.m60 - np.polyval(b, g.pre60)
    return s


def clustered(s, keys, cols):
    """Mean of each col per key group, with t clustered by match (eid)."""
    out = []
    for c in cols:
        d = s[keys + ["eid", c]].dropna()
        e = d.groupby(keys + ["eid"])[c].agg(["sum", "size"]).reset_index()
        tot = e.groupby(keys)[["sum", "size"]].sum().rename(columns={"sum": "S", "size": "N"})
        e = e.join(tot, on=keys)
        e["r"] = e.S / e.N
        e["dev2"] = (e["sum"] - e.r * e["size"]) ** 2
        g = e.groupby(keys).agg(G=("eid", "size"), dev2=("dev2", "sum"), S=("S", "first"), N=("N", "first"))
        mean = g.S / g.N
        var = g.G / (g.G - 1).clip(lower=1) * g.dev2 / g.N ** 2
        out.append(pd.DataFrame({c: mean, c + "_t": mean / np.sqrt(var.replace(0, np.nan)), c + "_n": g.N}))
    return pd.concat(out, axis=1)


def label(r):
    lead = r.m60_t >= T_SIG and r.res60_t >= T_SIG and r.m60 > r.pre60
    follow = r.pre60_t >= T_SIG and r.m60_t < 2
    liquid = r.roi > 0 and r.edge_t >= T_SIG and r.m60_t < 2 and r.taker_share < 0.5
    if lead:
        return "information leader"
    if follow:
        return "price follower"
    if liquid:
        return "liquidity-dependent"
    return "unclear"


def main():
    src, tiers, outdir = sys.argv[1:4]
    s = load(src, sys.argv[4:])
    cols = ["pre60", "edge", "res60", "roi"] + [f"m{h}" for h in H] + [f"drift{d}" for d in (5, 30, 120)] \
        + [f"cev{d}" for d in H] + [f"cnf{d}" for d in H]
    base = clustered(s, ["seg", "taker"], ["pre60", "edge"] + [f"m{h}" for h in H] + ["res60"])
    base.to_csv(f"{outdir}/baseline-by-market.csv")
    n = s.groupby(["wallet", "seg"]).size()
    keep = n[n >= MIN_SIGNALS].index
    w = s.set_index(["wallet", "seg"]).loc[keep].reset_index()
    r = clustered(w, ["wallet", "seg"], cols)
    r["signals"] = n.loc[r.index]
    r["taker_share"] = w.groupby(["wallet", "seg"]).taker.mean()
    r["usd"] = w.groupby(["wallet", "seg"]).usd.sum()
    r["last"] = pd.to_datetime(w.groupby(["wallet", "seg"]).ts.max(), unit="s").dt.date
    t = pd.read_csv(tiers).rename(columns={"market": "seg"}).set_index(["wallet", "seg"])
    r["tier"] = t.tier.reindex(r.index).fillna("untiered")
    r["class"] = r.apply(label, axis=1)
    r.to_csv(f"{outdir}/wallet-markets.csv")
    print(r.groupby(["tier", "class"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
