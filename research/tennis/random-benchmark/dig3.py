"""Biggest winning-record wallets after the split. Usage: dig3.py BETS.csv.gz FROZEN_LIST.csv"""
import sys, numpy as np, pandas as pd
SPLIT=1783036800
b=pd.read_csv(sys.argv[1],dtype={"eid":str}); b=b[(b.stake>0)&(b.phase=="pre")].copy()
b["q"]=b.stake/b.shares; b["won"]=b.pnl>0; b["pay"]=((b.pnl+b.fee)/b.shares+b.q).round(2)
tr,te=b[b.ts<SPLIT],b[(b.ts>=SPLIT)&(b.pay!=0.5)]
w=tr.groupby("wallet").agg(matches=("eid","nunique"),stake=("stake","sum"),pnl=("pnl","sum"),wins=("won","sum"),bets=("won","size"))
pool=w[(w.matches>=20)&(w.stake>=5000)]; sel=pool[(pool.pnl/pool.stake>0.05)&(pool.wins/pool.bets>0.6)].index
d=te[te.wallet.isin(sel)]
g=d.groupby("wallet").agg(st=("stake","sum"),pnl=("pnl","sum"),bets=("pnl","size"),taker=("taker_stake","sum")).sort_values("pnl")
g["roi"]=g.pnl/g.st; g["taker_share"]=g.taker/g.st
print(g.tail(6).round(3).to_string()); print("total pnl",round(g.pnl.sum()),"stake",round(g.st.sum()))
for k in (1,3,5):
    h=g.iloc[:-k]; print(f"dollar ROI excl top {k}: {h.pnl.sum()/h.st.sum():+.4f}")
print("selected taker share of stake:", round(d.taker_stake.sum()/d.stake.sum(),3), "| others:", round(te[te.wallet.isin(pool.index)&~te.wallet.isin(sel)].taker_stake.sum()/te[te.wallet.isin(pool.index)&~te.wallet.isin(sel)].stake.sum(),3))
fl=pd.read_csv(sys.argv[2]).wallet.str.lower()
print("top 5 on frozen list:", [x[:10] for x in g.index[-5:] if x in set(fl)], "| selected on frozen list:", sum(x in set(fl) for x in sel), "of", len(sel))
