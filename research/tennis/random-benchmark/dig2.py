"""Where the winning-record group's later returns come from. Usage: dig2.py BETS.csv.gz"""
import sys, numpy as np, pandas as pd
SPLIT=1783036800
b=pd.read_csv(sys.argv[1],dtype={"eid":str}); b=b[(b.stake>0)&(b.phase=="pre")].copy()
b["r"]=b.pnl/b.stake; b["q"]=b.stake/b.shares; b["won"]=b.pnl>0
b["pay"]=((b.pnl+b.fee)/b.shares+b.q).round(2)
tr,te=b[b.ts<SPLIT],b[b.ts>=SPLIT]
w=tr.groupby("wallet").agg(matches=("eid","nunique"),stake=("stake","sum"),pnl=("pnl","sum"),wins=("won","sum"),bets=("won","size"))
pool=w[(w.matches>=20)&(w.stake>=5000)]; sel=pool[(pool.pnl/pool.stake>0.05)&(pool.wins/pool.bets>0.6)].index
for nm,x in (("selected",te[te.wallet.isin(sel)]),("other eligible",te[te.wallet.isin(pool.index)&~te.wallet.isin(sel)])):
    m=x[(x.q>=.2)&(x.q<=.8)]
    print("==",nm,"20-80c bets",len(m),"payout mix",m.pay.value_counts(normalize=True).head(4).round(3).to_dict())
    print("  flat ROI all",round(m.r.mean(),4),"| excl 50-50",round(m[m.pay!=0.5].r.mean(),4),"| 50-50 share of bets",round((m.pay==0.5).mean(),3))
    e=m[m.pay!=0.5]
    for lo,hi in ((.2,.4),(.4,.6),(.6,.8)):
        y=e[(e.q>=lo)&(e.q<hi)]; print(f"  {lo:.0%}-{hi:.0%}: bets {len(y)}, win {y.won.mean():.3f}, avg price {y.q.mean():.3f}, flat ROI {y.r.mean():+.4f}")
    if nm=="selected":
        g=e.groupby("wallet").r.agg(["size","sum"]).sort_values("sum"); print("  top 5 wallets' share of summed returns:", round(g["sum"].tail(5).sum()/g["sum"].sum(),3), "wallets with + sum:",(g["sum"]>0).sum(),"of",len(g))
        print("  flat ROI excl top 3 wallets:", round(e[~e.wallet.isin(g.index[-3:])].r.mean(),4))
