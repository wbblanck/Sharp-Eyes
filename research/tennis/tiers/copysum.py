import sys, math, numpy as np, pandas as pd
d=pd.read_csv(sys.argv[1]); d["phase"]=d.market.str.split(" \\| ").str[1]
def rt(x,y):
    sy=y.sum(); r=x.sum()/sy; n=len(x)
    var=n/(n-1)*((x-r*y)**2).sum()/sy**2; return r, r/math.sqrt(var)
def summ(g):
    o={"bets":len(g),"own_roi":g.own_pnl.sum()/g.q.sum()}
    for dl in (30,120):
        h=g[g[f"c{dl}"].notna()]
        ev=h.groupby("eid")[[f"c{dl}",f"q{dl}"]].sum()
        r,t=rt(ev[f"c{dl}"].values,ev[f"q{dl}"].values) if len(ev)>2 else (np.nan,np.nan)
        o[f"copied_{dl}s"]=len(h); o[f"roi_{dl}s"]=round(r,4); o[f"t_{dl}s"]=round(t,2)
    return pd.Series(o)
pd.set_option("display.width",250)
print(d.groupby(["tier","phase","maker"]).apply(summ).to_string())
print(d.groupby(["phase"]).apply(summ).to_string())
w=d.groupby(["wallet","market","tier","maker"]).apply(summ).reset_index()
w=w[w.copied_30s>=50].sort_values("t_30s",ascending=False)
print(len(w), "wallet-markets with 50+ copies; roi_30s>0:", (w.roi_30s>0).sum(), " t_30s>2:", (w.t_30s>2).sum(), " roi_120s>0:", (w.roi_120s>0).sum(), " both t>2:", ((w.t_30s>2)&(w.t_120s>2)).sum())
print(w.head(15).assign(wallet=w.wallet.str[:10]).to_string())
w.to_csv(sys.argv[2],index=False,float_format="%.4f")
