"""Resting-order line of the tennis paper test (Will chose 2026-11-11).

Takes the whole-list 30 s and 2 min copies already priced by book_check.py
(paper-bets-book.csv) and keeps only the bets where the sharp's own fill was a
resting (maker) order, read from the fills' taker flag. Prints totals since the
freeze and since 2026-11-11 16:53Z (the real test: the line was chosen after the
first 25 such bets were seen).

Usage: python3 -I maker_line.py <data-dir>   (e.g. data/paper-tennis)
"""

import collections
import csv
import glob
import gzip
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
REAL_TEST_FROM = "2026-11-11T16:53"
D = Path(sys.argv[1])

cid2e = {}
for f in glob.glob(str(D / "events" / "*.json")):
    e = json.load(open(f))
    for m in e["markets"]:
        cid2e[m["conditionId"]] = e["id"]

book = {}
for r in csv.DictReader(open(HERE / "paper-bets-book.csv")):
    if r["group"] != "list":
        continue
    try:
        book[(r["delay_s"], r["wallet"], r["match"], r["market"], r["pick"])] = float(r["book_profit_usd"])
    except ValueError:
        book[(r["delay_s"], r["wallet"], r["match"], r["market"], r["pick"])] = None

cache = {}


def fills(eid):
    if eid not in cache:
        d = collections.defaultdict(set)
        with gzip.open(D / "fills" / f"{eid}.jsonl.gz", "rt") as fh:
            for line in fh:
                t, w, c, _o, _s, _p, _sz, tk = json.loads(line)
                d[(w, c, t)].add(tk)
        cache[eid] = d
    return cache[eid]


rows = collections.defaultdict(list)  # (delay, period) -> bets
for x in json.load(open(HERE / "bets-full.json"))["list"]:
    eid = cid2e.get(x["cid"])
    if eid is None:
        continue
    if fills(eid).get((x["wallet"], x["cid"], x["wallet_ts"])) != {0}:
        continue  # keep only fills that were entirely resting orders
    k = (str(x["delay_s"]), x["wallet"], x["match"], x["market"], x["pick"])
    x["book"] = book.get(k)
    rows[(x["delay_s"], "since freeze")].append(x)
    if x["match_start_utc"] >= REAL_TEST_FROM:
        rows[(x["delay_s"], "since Nov 11 (real test)")].append(x)

for (delay, period), g in sorted(rows.items()):
    priced = [x for x in g if x["book"] is not None]
    nv = [x for x in g if x["result"] != "void"]
    w = sum(x["result"] == "won" for x in nv)
    v = len(g) - len(nv)
    e = [x["payout"] - x["wallet_price"] for x in g]
    m = sum(e) / len(e)
    sd = math.sqrt(sum((a - m) ** 2 for a in e) / (len(e) - 1)) if len(e) > 1 else 0
    t = f"{m / sd * math.sqrt(len(e)):+.1f}" if sd else "-"
    bk = sum(x["book"] for x in priced)
    roi = f"{bk / 5 / len(priced) * 100:+.1f}%" if priced else "-"
    print(
        f"resting-order {delay}s {period}: {len(g)} bets {w}-{len(nv) - w} +{v} settled 50-50; "
        f"real book ${bk:+.2f} on {len(priced)} priced ({roi}); "
        f"picks vs sharp's own price {m * 100:+.1f}c/share (t {t})"
    )
if not rows:
    print("resting-order: no bets")
