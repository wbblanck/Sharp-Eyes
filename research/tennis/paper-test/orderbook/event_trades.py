import json,sys,urllib.request,urllib.parse,datetime as dt
eid,cid,wallet,outcome=sys.argv[1:5]
rows=[];cur=None
while True:
    p={"event_id":eid,"limit":500,"taker_only":"false"}
    if cur: p["cursor"]=cur
    b=json.load(urllib.request.urlopen(urllib.request.Request("https://data-api.polymarket.com/v2/trades?"+urllib.parse.urlencode(p),headers={"User-Agent":"sharp-eyes-research/0.1"}),timeout=30))
    rows+=b.get("data") or []
    cur=(b.get("pagination") or {}).get("next_cursor")
    if not cur or not b.get("data"): break
rows=[r for r in rows if r['condition_id']==cid]
rows.sort(key=lambda r:r['timestamp'])
json.dump(rows,open(f"trades_{eid}.json","w"))
fb=[r for r in rows if r['proxy_wallet'].lower().startswith(wallet) and r['outcome']==outcome and r['side']=='BUY']
t0=fb[0]['timestamp']
f=lambda t:dt.datetime.fromtimestamp(t,dt.UTC).strftime('%m-%d %H:%M:%S')
print('rows',len(rows),'first list buy',f(t0),fb[0]['price'],fb[0]['size'])
for r in rows:
    if t0-60<=r['timestamp']<=t0+150:
        print(f(r['timestamp']), r['outcome'][:14].ljust(14), r['side'].ljust(4), r['price'], r['size'], r['proxy_wallet'][:8], r['transaction_hash'][:10])
