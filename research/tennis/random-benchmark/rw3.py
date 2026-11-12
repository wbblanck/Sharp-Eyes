"""Random-wallet benchmark (12 Nov 2026). Usage: rw2.py BETS.csv.gz TIERS_BEFORE.csv OUT.json
rw3.py is the same with bets that settled 50-50 left out of the later period."""
import json, sys, numpy as np, pandas as pd
SPLIT=1783036800; DRAWS=2000; rng=np.random.default_rng(7)
b=pd.read_csv(sys.argv[1],dtype={"eid":str}); b=b[b.stake>0].copy()
b["market"]=b.tour+" | "+np.where(b.phase=="pre","pre-match","in-play")+" | "+b.kind
b["r"]=b.pnl/b.stake; b["q"]=b.stake/b.shares; b["won"]=b.pnl>0; b["pay"]=((b.pnl+b.fee)/b.shares+b.q).round(2)
tr,te=b[b.ts<SPLIT],b[(b.ts>=SPLIT)&(b.pay!=0.5)]
def bench(selkeys,pool,keys,test,strata,label):
    t=test.copy(); t["mid"]=(t.q>=0.2)&(t.q<=0.8)
    t["rm"]=np.where(t.mid,t.r,0.0)
    per=t.groupby(keys).agg(rs=("r","sum"),n=("r","size"),pnl=("pnl","sum"),st=("stake","sum"),rm=("rm","sum"),nm=("mid","sum"))
    pool=pool[pool.index.isin(per.index)]; sel=pool[pool.index.isin(selkeys)]; p=per.reindex(pool.index)
    p["wroi"]=p.pnl/p.st
    def stat(idx):
        x=p.loc[idx]
        return np.array([x.rm.sum()/x.nm.sum(), x.pnl.sum()/x.st.sum(), (x.wroi>0).mean(), x.wroi.median()])
    s=stat(sel.index)
    T=lambda k: k if isinstance(k,tuple) else (k,)
    groups={T(k):g.index.values for k,g in pool.groupby(strata)}; need=sel.groupby(strata).size()
    R=[]
    for _ in range(DRAWS):
        idx=[]
        for k,n in need.items():
            c=groups[T(k)]; idx.extend(rng.choice(len(c),size=n,replace=len(c)<n).tolist() and [c[i] for i in rng.choice(len(c),size=n,replace=len(c)<n)])
        R.append(stat(pd.Index(idx) if len(keys)==1 else pd.MultiIndex.from_tuples(idx)))
    R=np.array(R); names=["flat ROI 20-80c bets","dollar ROI","share of wallets profitable","median wallet ROI"]
    print(f"== {label}: {len(sel)} selected of {len(pool)} eligible, {int(p.loc[sel.index].n.sum())} later bets")
    res={}
    for i,nm in enumerate(names):
        res[nm]=dict(selected=round(float(s[i]),4),random_mean=round(float(R[:,i].mean()),4),random_5_95=[round(float(np.percentile(R[:,i],5)),4),round(float(np.percentile(R[:,i],95)),4)],share_random_as_good=round(float((R[:,i]>=s[i]).mean()),3))
        print(f"  {nm}: selected {s[i]:+.4f} | random mean {R[:,i].mean():+.4f} (5-95%: {np.percentile(R[:,i],5):+.4f} to {np.percentile(R[:,i],95):+.4f}) | random as good: {(R[:,i]>=s[i]).mean():.1%}")
    return res
out={}
pre_tr,pre_te=tr[tr.phase=="pre"],te[te.phase=="pre"]
w=pre_tr.groupby("wallet").agg(matches=("eid","nunique"),stake=("stake","sum"),pnl=("pnl","sum"),wins=("won","sum"),bets=("won","size"),shares=("shares","sum"))
pool=w[(w.matches>=20)&(w.stake>=5000)].copy()
pool["qb"]=pd.cut(pool.stake/pool.shares,[0,.3,.4,.5,.6,.7,.8,1.01],labels=False); pool["sb"]=pd.qcut(np.log(pool.stake),4,labels=False)
sel=pool[(pool.pnl/pool.stake>0.05)&(pool.wins/pool.bets>0.6)].index
out["winning_record"]=bench(sel,pool,["wallet"],pre_te,["qb","sb"],"Winning-record rule (frozen-list rule), pre-match")
t=pd.read_csv(sys.argv[2])
wm=tr.groupby(["wallet","market"]).agg(bets=("r","size"),stake=("stake","sum"),shares=("shares","sum"))
wm=wm[wm.bets>=300].copy(); wm["qb"]=pd.cut(wm.stake/wm.shares,[0,.3,.4,.5,.6,.7,.8,1.01],labels=False); wm["bb"]=(wm.bets>=500).astype(int)
wm=wm.reset_index(); wm["mk"]=wm.market; wm=wm.set_index(["wallet","market"])
for lab,tiers in (("Tier 1",["Tier 1"]),("Tier 2",["Tier 2"]),("Tier 1+2",["Tier 1","Tier 2"])):
    keys=pd.MultiIndex.from_frame(t[t.tier.isin(tiers)][["wallet","market"]])
    out[lab]=bench(keys,wm,["wallet","market"],te,["mk","qb","bb"],f"{lab} (picked before 3 Jul), same market")
json.dump(out,open(sys.argv[3],"w"),indent=1)
