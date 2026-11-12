import sys, numpy as np, pandas as pd
S=sys.argv[1]
b=pd.read_csv(f"{S}/bets.csv.gz",dtype={"eid":str}); b=b[(b.ts>=1783036800)&(b.stake>0)]
b["market"]=b.tour+" | "+np.where(b.phase=="pre","pre-match","in-play")+" | "+b.kind
t=pd.read_csv(f"{S}/pre/wallet-markets.csv"); t["tier"]=t.tier.fillna("untiered")
g=b.groupby(["wallet","market"])[["pnl","stake","taker_stake"]].sum().reset_index()
m=g.merge(t[["wallet","market","tier","taker_share"]],on=["wallet","market"])
m["roi"]=m.pnl/m.stake
print(m.groupby("tier").agg(n=("roi","size"),pos=("roi",lambda s:(s>0).mean())))
# maker vs taker among tiered
m["maker"]=m.taker_share<0.5
print(m[m.tier!="untiered"].groupby(["tier","maker"]).agg(n=("roi","size"),pos=("roi",lambda s:(s>0).mean()),pnl=("pnl","sum"),stake=("stake","sum")))
f=pd.read_csv(f"{S}/full/wallet-markets.csv"); f1=f[f.tier.notna()]
print("full tiers maker share<50%:", f1.assign(mk=f1.taker_share<0.5).groupby("tier").mk.agg(["sum","size"]))
print("n>=500 tested:", (f.bets>=500).sum(), " n 300-499:", ((f.bets>=300)&(f.bets<500)).sum(), " 100-299:", (f.bets<300).sum())
