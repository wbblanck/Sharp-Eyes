"""Forward paper test (Will, 11 Nov): copy the FIRST sharp wallet in, in-play, at 10-30c.

Frozen rule (set 11 Nov 2026 from the 8 Nov follow-up, nothing tuned after):
  sharp set   frozen-sharp-set.csv (leaders + Tier 1/2 picked on data before 3 Jul 2026), wallet x market
  signal      first fill of a new position by a sharp wallet in its sharp market, during play
  first in    no OTHER sharp wallet opened the same market and side in the 120 s before
  price       market mid (trade-based, as in signals.py) at the signal between 10c and 30c
  window      signals from 2026-11-07 00:00 UTC to 2026-11-27 00:00 UTC
Copy: $5 at 5 s, 15 s and 30 s after the signal.
  book    walk the real ask book (PendulumFlow archive) at that moment, fee 0.05*p*(1-p) per share level by level
  tape    next ask printed at/after that moment (generous; kept for comparison)
Book times: archive clock runs ~2.2 s behind the Data API trade second (measured 7 Nov), so book time = ts + d - 2.2.
Usage (from the repo root):
  uv run sharp-eyes history-fetch --sport tennis --min-volume 50000 --since 2026-11-06 --rate 40 --concurrency 16
  BOOK_TMP=/some/tmp uv run --with duckdb --with pandas --with numpy python scripts/tennis-signal/forward.py OUT_DIR"""
import csv, importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
sys.argv, OUT = [sys.argv[0], "data/history-tennis", "/dev/null"], Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("signals", HERE / "signals.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
BOOKCHECK = Path("/mnt/project-files/sharp-traders/tennis/paper-test/orderbook/book_check.py")
spec = importlib.util.spec_from_file_location("book_check", BOOKCHECK)
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
from sharp_eyes.history.analyze import parse_ts
from sharp_eyes.history.fetch import HistoryCache

START = datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp()
END = datetime(2026, 11, 27, tzinfo=timezone.utc).timestamp()
DELAYS = (5, 15, 30)
UNIT = 5.0
FEE = 0.05
OFFSET = -2.2
WIN = 120

sharp = pd.read_csv(OUT / "frozen-sharp-set.csv")
SH = set(zip(sharp.wallet, sharp.seg))
cache = HistoryCache(Path("data/history-tennis"))
rows = []
for eid in cache.event_ids():
    ev = cache.load_event(eid)
    st = parse_ts(ev.get("startTime"))
    if st is None or st < START - 86400 or st >= END + 86400:
        continue
    for r in S.one(eid):
        rows.append(dict(zip(S.COLS, r)) | {"title": ev.get("title", "")})
s = pd.DataFrame(rows)
if s.empty:
    sys.exit("no matches in the window yet")
s["seg"] = s.tour + " | " + np.where(s.phase == "pre", "pre-match", "in-play") + " | " + s.kind
s = s[[(w, g) in SH for w, g in zip(s.wallet, s.seg)]].sort_values(["cid", "phase", "k", "ts"])
s["first"] = False
for _, g in s.groupby(["cid", "phase", "k"]):
    ts, w = g.ts.to_numpy(), g.wallet.to_numpy()
    for i, idx in enumerate(g.index):
        lo = np.searchsorted(ts, ts[i] - WIN, "left")
        s.at[idx, "first"] = not any(x != w[i] for x in w[lo:i])
mid0 = pd.to_numeric(s.mid0, errors="coerce")
p = s[(s.phase == "live") & s["first"] & (mid0 >= 0.10) & (mid0 < 0.30) & (s.ts >= START) & (s.ts < END)].copy()
tok = B.tokens(set(p.cid))
bets = []
for r in p.itertuples():
    for d in DELAYS:
        c = r._asdict()
        cq = c.get(f"c{d}")
        cq = None if cq in ("", None) or (isinstance(cq, float) and np.isnan(cq)) else float(cq)
        b = {"match": r.title, "market": r.kind, "wallet": r.wallet, "group": sharp.set_index(["wallet", "seg"]).group.get((r.wallet, r.seg)),
             "signal_utc": datetime.fromtimestamp(r.ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "delay_s": d,
             "mid_at_signal": r.mid0, "wallet_price": r.q, "payout": r.pay,
             "tape_price": cq, "tape_profit_usd": None if cq is None else round(UNIT / cq * (r.pay - cq - FEE * cq * (1 - cq)), 2),
             "cid": r.cid, "k": r.k, "token": tok[r.cid][r.k], "copy_ts": r.ts + d + OFFSET, "fee_rate": FEE, "fee_exp": 1}
        bets.append(b)
import duckdb
con = duckdb.connect()
B.EXT.mkdir(exist_ok=True)
B.fetch_hours(bets, con)
for b in bets:
    b.update(B.price(b | {"payout": b["payout"]}, con))
out = pd.DataFrame(bets).drop(columns=["token", "copy_ts", "fee_rate", "fee_exp"])
out.to_csv(OUT / "forward-bets.csv", index=False)
lines = [f"# Forward paper test: first sharp in, in-play, 10-30c (updated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
         f"Signals {datetime.fromtimestamp(START, timezone.utc):%d %b} to {datetime.fromtimestamp(min(END, p.ts.max() if len(p) else START), timezone.utc):%d %b %H:%M} UTC; $5 per bet, fee included.", "",
         "| Delay | Bets | Real book: priced | Won-lost | Real book profit | ROI | Book could not fill $5 | Next-trade profit |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
for d in DELAYS:
    o = out[out.delay_s == d]
    ok = o[o.book_status == "ok"]
    wl = f"{(ok.payout == 1).sum()}-{(ok.payout == 0).sum()}" + (f" +{(ok.payout == 0.5).sum()} void" if (ok.payout == 0.5).any() else "")
    prof = ok.book_profit_usd.sum(); spent = ok.book_filled_usd.sum()
    lines.append(f"| {d} s | {len(o)} | {len(ok)} | {wl} | ${prof:+.2f} | {prof / spent * 100 if spent else 0:+.1f}% | "
                 f"{(ok.book_filled_usd < UNIT - 0.01).sum()} | ${o.tape_profit_usd.sum():+.2f} |")
pend = (out.book_status != "ok").sum()
lines += ["", f"Not yet priced from the book (archive runs about a day behind, or no book data): {pend} bet-delays.", "",
          "Per bet: forward-bets.csv. Rule and method: top of forward.py."]
(OUT / "forward-summary.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
