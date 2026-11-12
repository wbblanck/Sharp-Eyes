import duckdb,sys
f,cid,tok,t_lo,t_hi=sys.argv[1:6]
tokhex='%064X'%int(tok)
c=duckdb.connect()
q=f"""SELECT strftime(timezone('UTC',timestamp),'%H:%M:%S.%g') ts, event_type, side, price, size, best_bid, best_ask, transaction_hash
 FROM '{f}' WHERE market = from_hex('{cid[2:]}') AND asset_id = from_hex('{tokhex}')
 AND event_type IN ('price_change','last_trade_price','best_bid_ask')
 AND timestamp BETWEEN TIMESTAMPTZ '{t_lo}' AND TIMESTAMPTZ '{t_hi}' ORDER BY timestamp, row_ordinal"""
for r in c.sql(q).fetchall():
    ts,et,side,p,s,bb,ba,tx=r
    if et=='price_change' and side=='BUY' and len(sys.argv)<7: continue
    print(ts, et[:5], side or '', p if p is not None else '', s if s is not None else '', '| bid',bb,'ask',ba, (tx.hex()[:10] if tx else ''))
