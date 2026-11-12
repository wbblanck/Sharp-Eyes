"""First-in sharp signals: in-play price buckets vs everyone else, by month, and on the real order book.
Run after order.py and book_signals.py (paths are the defaults used in README)."""
import sys; sys.path.insert(0,"scripts/tennis-signal")
import pandas as pd, numpy as np
from classify import clustered
s=pd.read_csv("data/signals.csv.gz",dtype={"eid":str})
s=s[(s.ts>=1783036800)&(s.phase=="live")&(s.kind=="moneyline")]
for d in (5,30):
    c=s[f"c{d}"]; s[f"cev{d}"]=(s.pay-c-0.05*c*(1-c))/c
s["px"]=pd.cut(s.mid0,[0,.1,.2,.3,.7,1],labels=["<10c","10-20c","20-30c","30-70c",">70c"])
o=pd.read_csv("data/out/order/order-signals.csv.gz")
s=s.merge(o[["wallet","cid","phase","k","ts","role"]],on=["wallet","cid","phase","k","ts"],how="left")
s["who"]=np.where(s.role.isna(),"everyone else",np.where(s.role.isin(["alone","first, others followed"]),"sharp first in","sharp later"))
r=clustered(s,["px","who"],["cev5","cev30"])
pd.set_option("display.width",250); print(r.round(4).to_string())

import sys; sys.path.insert(0,"scripts/tennis-signal")
import pandas as pd, numpy as np
from classify import clustered
o=pd.read_csv("data/out/order/order-signals.csv.gz")
o["first"]=o.role.isin(["alone","first, others followed"])
s=pd.read_csv("data/signals.csv.gz",dtype={"eid":str})
s=s.merge(o[["wallet","cid","phase","k","ts","first","group"]],on=["wallet","cid","phase","k","ts"])
s=s[(s.phase=="live")&s["first"]&(s.mid0<0.30)&(s.mid0>=0.10)]
for d in (5,15,30,60):
    c=s[f"c{d}"]; s[f"cev{d}"]=(s.pay-c-0.05*c*(1-c))/c
s["month"]=pd.to_datetime(s.ts,unit="s").dt.to_period("M").astype(str)
pd.set_option("display.width",250)
print(clustered(s,["month"],["cev5","cev30"]).round(3).to_string())
print(clustered(s,["group"],["cev5","cev30"]).round(3).to_string())
print(clustered(s,["taker"],["cev5","cev30"]).round(3).to_string())
s["one"]=1; print(clustered(s,["one"],["cev5","cev15","cev30","cev60"]).round(4).to_string())
print("wallets:",s.wallet.nunique()); print(s.groupby("wallet").size().sort_values(ascending=False).head(5)/len(s))
# real order book window
b=pd.read_csv("data/book-signals.csv.gz",dtype={"eid":str})
b=b.merge(o[["wallet","cid","phase","k","ts","first"]],on=["wallet","cid","phase","k","ts"])
b=b[(b.phase=="live")&b["first"]&(b.bmid0<0.30)&(b.bmid0>=0.10)]
for d in (5,15,30,60):
    a=b[f"ba{d}"]; b[f"bev{d}"]=(b.pay-a-0.05*a*(1-a))/a
b["one"]=1; print("BOOK", clustered(b,["one"],["bev5","bev15","bev30","bev60"]).round(4).to_string())
