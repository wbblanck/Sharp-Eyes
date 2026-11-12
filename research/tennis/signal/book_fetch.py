"""Download every hourly PendulumFlow v3.1 sports file in the archive (free,
CC BY-NC 4.0, credit pendulumflow), keep only tennis best bid / best ask
changes and trade prints (.trades), delete the big file. Output: OUT_DIR/<hour>.parquet with
t_us, market (hex condition id), asset (token id hex), bid, ask.
Usage: book_fetch.py OUT_DIR TMP_DIR"""
import os, subprocess, sys, time, urllib.request
from pathlib import Path
import duckdb

UA = "sharp-eyes-research/0.1"
ARCHIVE = "https://dl.pendulumflow.com/v3.1/"
SUMS = "https://archive.pendulumflow.com/v3.1/SHA256SUMS.txt"
out, tmp = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True); tmp.mkdir(parents=True, exist_ok=True)
sums = {}
for line in urllib.request.urlopen(urllib.request.Request(SUMS, headers={"User-Agent": UA})).read().decode().splitlines():
    if line.strip() and not line.startswith("#"):
        h, p = line.split()
        if p.endswith(".sports.parquet"):
            sums[p] = h
con = duckdb.connect()
for p in sorted(sums):
    dest = out / (os.path.basename(p).replace(".sports", ""))
    if dest.exists():
        continue
    f = tmp / "h.parquet"
    for attempt in range(6):
        rc = subprocess.run(["curl", "-sS", "-f", "-m", "900", "-A", UA, "-o", str(f), ARCHIVE + p]).returncode
        if rc == 0 and subprocess.run(["sha256sum", str(f)], capture_output=True, text=True).stdout.split()[0] == sums[p]:
            break
        time.sleep(60)
    else:
        print("FAILED", p, flush=True); continue
    con.sql(f"""COPY (SELECT epoch_us(timestamp) t_us, hex(market) market, hex(asset_id) asset,
        best_bid::DOUBLE bid, best_ask::DOUBLE ask FROM '{f}'
        WHERE event_type='best_bid_ask' AND sub_tag='tennis' ORDER BY t_us, row_ordinal)
        TO '{dest}.tmp' (FORMAT parquet)""")
    con.sql(f"""COPY (SELECT epoch_us(timestamp) t_us, hex(market) market, hex(asset_id) asset,
        price::DOUBLE price, size::DOUBLE size, side FROM '{f}'
        WHERE event_type='last_trade_price' AND sub_tag='tennis' ORDER BY t_us, row_ordinal)
        TO '{dest}.trades' (FORMAT parquet)""")
    os.replace(f"{dest}.tmp", dest)
    f.unlink()
    print("ok", p, flush=True)
    time.sleep(1)
