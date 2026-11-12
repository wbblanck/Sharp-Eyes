"""Re-price every paper bet from the real Polymarket order book (Will, 5 Nov).

paper_test.py prices a copy at the first trade printed after the delay. In thin
markets that trade can be a few shares nobody else could get. This script asks
instead: what would a $5 market buy at the copy time really have paid, given the
offers on the book then?

Book data: PendulumFlow archive v3.1 (free, CC BY-NC 4.0, credit pendulumflow),
one sports file per hour. For each hour a copy falls in, the sports file and the
hour's opening book are downloaded once, cut down to our tokens, and kept in
ext/ (a few KB each); the big files are deleted.

Ask book at copy time T = opening book for that token, replaced by any full book
snapshot and updated by each ask-side price change up to T. The $5 buy walks
the asks from the cheapest up; the taker fee is added level by level.

Usage (after paper_test.py has written bets-full.json):
    python3 -I orderbook/book_check.py
Needs: pip install duckdb. Writes paper-bets-book.csv and prints the totals.
"""
import csv, datetime as dt, json, os, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
TEST = HERE.parent
EXT = HERE / "ext"
TMP = Path(os.environ.get("BOOK_TMP", "/tmp/book-check-dl"))
UA = "sharp-eyes-research/0.1"
ARCHIVE = "https://dl.pendulumflow.com/v3.1/"
SUMS = "https://archive.pendulumflow.com/v3.1/SHA256SUMS.txt"
UNIT = 5.0
BIG_WIN = 20.0


def http(url: str) -> bytes:
    for _ in range(6):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
        except Exception as e:  # rate limit (429) or a dropped connection: wait, retry
            print("retry", url, e, file=sys.stderr)
            time.sleep(60)
    raise SystemExit("failed " + url)


def tokens(cids: set[str]) -> dict[str, list[str]]:
    cache_f = EXT / "tokens.json"
    tok = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    todo = sorted(c for c in cids if c not in tok)
    for i in range(0, len(todo), 20):
        q = urllib.parse.urlencode([("condition_ids", c) for c in todo[i:i + 20]] + [("limit", 100), ("closed", "true")])
        for m in json.loads(http("https://gamma-api.polymarket.com/markets?" + q)):
            tok[m["conditionId"]] = json.loads(m["clobTokenIds"])
    cache_f.write_text(json.dumps(tok))
    return tok


def download(path: str, sums: dict[str, str]) -> Path:
    dest = TMP / os.path.basename(path)
    for _ in range(6):
        rc = subprocess.run(["curl", "-sS", "-f", "-m", "900", "-A", UA, "-o", str(dest), ARCHIVE + path]).returncode
        if rc == 0:
            got = subprocess.run(["sha256sum", str(dest)], capture_output=True, text=True).stdout.split()[0]
            if got == sums.get(path):
                return dest
        time.sleep(60)
    raise SystemExit("failed " + path)


def hour_of(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.UTC).strftime("%Y-%m-%d/%H/%Y-%m-%dT%H")


def fetch_hours(bets: list[dict], con) -> None:
    need: dict[str, set[str]] = {}
    for r in bets:
        need.setdefault(hour_of(r["copy_ts"]), set()).add(r["token"])
    todo = {}
    for h, toks in need.items():
        f = EXT / (os.path.basename(h) + ".parquet")
        have = set(json.loads((EXT / (os.path.basename(h) + ".tokens")).read_text())) if f.exists() else set()
        if not toks <= have:
            todo[h] = toks | have
    if not todo:
        return
    TMP.mkdir(parents=True, exist_ok=True)
    sums = {}
    for line in http(SUMS).decode().splitlines():
        if line.strip() and not line.startswith("#"):
            hsh, p = line.split()
            sums[p] = hsh
    for h, toks in sorted(todo.items()):
        if h + ".sports.parquet" not in sums:
            print("not in archive yet:", h, file=sys.stderr)
            continue
        base = EXT / os.path.basename(h)
        tl = ",".join(f"from_hex('{int(t):064X}')" for t in toks)
        f = download(h + ".sports.parquet", sums)
        con.sql(f"""COPY (SELECT event_type, epoch_us(timestamp) t_us, row_ordinal, asset_id, side, price, size, asks
            FROM '{f}' WHERE asset_id IN ({tl}) AND event_type IN ('book','price_change'))
            TO '{base}.parquet.tmp' (FORMAT parquet)""")
        f.unlink()
        o = download(h + ".opening_state.parquet", sums)
        con.sql(f"COPY (SELECT asset_id, asks FROM '{o}' WHERE asset_id IN ({tl})) TO '{base}.parquet.open' (FORMAT parquet)")
        o.unlink()
        os.replace(f"{base}.parquet.tmp", f"{base}.parquet")
        Path(f"{base}.tokens").write_text(json.dumps(sorted(toks)))
        print("fetched", h, file=sys.stderr)
        time.sleep(2)


def asks_at(r: dict, con):
    t_us = int(r["copy_ts"] * 1e6)
    th = f"{int(r['token']):064X}"
    f = EXT / (os.path.basename(hour_of(r["copy_ts"])) + ".parquet")
    if not f.exists():
        return None
    book: dict[float, float] = {}
    o = con.sql(f"SELECT asks FROM read_parquet('{f}.open') WHERE asset_id=from_hex('{th}')").fetchall()
    if o and o[0][0] is not None:
        book = {float(x["price"]): float(x["size"]) for x in o[0][0]}
    ev = con.sql(f"""SELECT event_type, side, price, size, asks FROM '{f}' WHERE asset_id=from_hex('{th}')
        AND t_us <= {t_us} ORDER BY t_us, row_ordinal""").fetchall()
    for et, side, p, s, asks in ev:
        if et == "book":
            book = {float(x["price"]): float(x["size"]) for x in (asks or [])}
        elif side == "SELL":
            book[float(p)] = float(s)
    return {p: s for p, s in book.items() if s > 0}


def price(r: dict, con) -> dict:
    book = asks_at(r, con)
    if not book:
        return {"book_status": "no book data" if book is None else "no offers"}
    spend = shares = fee = 0.0
    for p in sorted(book):
        if spend >= UNIT - 1e-9:
            break
        take = min(book[p], (UNIT - spend) / p)
        shares += take
        spend += take * p
        fee += r["fee_rate"] * take * (p * (1 - p)) ** r["fee_exp"]
    best = min(book)
    return {
        "book_status": "ok", "best_ask": best, "offered_at_best_usd": round(best * book[best], 2),
        "book_avg_price": round(spend / shares, 4), "book_filled_usd": round(spend, 2),
        "book_fee": round(fee, 4), "book_profit_usd": round(shares * r["payout"] - spend - fee, 2),
    }


def main() -> None:
    allb = json.loads((TEST / "bets-full.json").read_text())
    EXT.mkdir(exist_ok=True)
    tok = tokens({r["cid"] for g in allb.values() for r in g})
    for g in allb.values():
        for r in g:
            r["token"] = tok[r["cid"]][r["k"]]
    con = duckdb.connect()
    fetch_hours([r for g in allb.values() for r in g], con)
    out = []
    for g, rows in allb.items():
        for r in rows:
            out.append({"group": g, **{k: r[k] for k in ("delay_s", "match_start_utc", "match", "market", "pick", "wallet",
                        "copy_price", "result", "profit_usd")}, **price(r, con)})
    keys = list(dict.fromkeys(k for r in out for k in r))
    with open(TEST / "paper-bets-book.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(out)
    for g in allb:
        for d in (30, 120):
            rs = [r for r in out if r["group"] == g and r["delay_s"] == d]
            ok = [r for r in rs if r["book_status"] == "ok"]
            if not rs:
                continue
            old = sum(r["profit_usd"] for r in ok)
            new = sum(r["book_profit_usd"] for r in ok)
            short = sum(1 for r in ok if r["book_filled_usd"] < UNIT - 0.01)
            print(f"{g} {d} s: {len(ok)} of {len(rs)} bets priced from the book. "
                  f"Next-trade price ${old:+.2f}, real book price ${new:+.2f} "
                  f"({short} bets the book could not fill to $5). "
                  f"{len(rs) - len(ok)} bets with no book data (next-trade price ${sum(r['profit_usd'] for r in rs if r['book_status'] != 'ok'):+.2f}).")


if __name__ == "__main__":
    main()
