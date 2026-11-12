"""Paper test of the frozen tennis winning-record list, $5 flat per copied bet.

Run from the Sharp-Eyes repo (branch claude/project-thread-8hvswj or later):

    uv run sharp-eyes history-fetch --sport tennis --since 2026-10-29 \
        --data-dir data/paper-tennis --concurrency 16 --rate 40
    uv run python research/tennis/paper-test/paper_test.py \
        data/paper-tennis

Rules (stated to Will 2026-10-29):
* Only matches whose listed start is after the list was frozen (2026-10-29 14:10 UTC).
* One copied bet per pick (market and side), whatever the number of list
  wallets behind it, timed on the earliest list wallet's first pre-match buy.
  A market where list wallets back opposite sides is skipped (Will, 30 Oct).
* The copy buys at the first trade printed DELAY seconds after the wallet's
  trade, before the match starts. No print in time: no bet.
* Stake $5 (1 unit). Taker fee at that market's rate is added on top.
* Settled at the market's result. A market resolved 50-50 pays 50c a share and is
  reported as a void, outside the win-loss record (Will, 3 Nov), but its real
  profit or loss stays in the totals (50c a share is not a refund).
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sharp_eyes.history.analyze import (
    PRICE_CAP,
    PRICE_FLOOR,
    follower_fee,
    parse_markets,
    parse_ts,
    price_paths,
    tennis_cutoffs,
)
from sharp_eyes.history.fetch import HistoryCache

HERE = Path(__file__).parent
FROZEN_AT = parse_ts("2026-10-29T14:10:00Z") or 0.0
UNIT = 5.0
DELAYS = (30.0, 120.0)
BIG_WIN = 20.0  # profit on one $5 bet above this is shown apart in the summary
# Watch group (Will, 30 Oct and 6 Nov): wallets counted on their own, one per line in
# watch-wallets.txt next to this file. Kept out of the public repo, like the frozen list.
_WF = HERE / "watch-wallets.txt"
WATCH = {l.strip().lower() for l in _WF.read_text().splitlines() if l.strip()} if _WF.exists() else set()


def outcome_name(event: dict, cid: str, k: int) -> str:
    for m in event.get("markets") or []:
        if m.get("conditionId") == cid:
            try:
                return str(json.loads(m.get("outcomes") or "[]")[k])
            except (ValueError, IndexError):
                return str(k)
    return str(k)


def result_word(payout: float) -> str:
    return {1.0: "won", 0.0: "lost"}.get(payout, "void")


def table(rows: list[dict]) -> list[str]:
    """One line per bet (30 s copy), with its fee and the 2 min result."""
    et = ZoneInfo("America/New_York")
    late = {(r["match"], r["wallet"], r["market"]): r for r in rows if r["delay_s"] == 120}
    out = [
        "| # | Start (ET) | Match | Pick | Sharp paid | You paid | Result | Fee "
        "| Profit after fee | Profit after fee (2 min) | Wallet |",
        "|---:|---|---|---|---:|---:|---|---:|---:|---:|---|",
    ]
    tot = tot2 = fees = 0.0
    fast = [r for r in rows if r["delay_s"] == 30]
    for i, r in enumerate(fast, 1):
        start = datetime.fromisoformat(r["match_start_utc"].replace("Z", "+00:00"))
        r2 = late.get((r["match"], r["wallet"], r["market"]))
        tot += r["profit_usd"]
        fees += r["fee"]
        tot2 += r2["profit_usd"] if r2 else 0.0
        out.append(
            f"| {i} | {start.astimezone(et):%b %d %I:%M %p} | {r['match'].split(': ', 1)[-1]} "
            f"| {r['pick']} | {r['wallet_price'] * 100:.0f}c | {r['copy_price'] * 100:.0f}c "
            f"| {r['result']} | ${r['fee']:.2f} | ${r['profit_usd']:+.2f} "
            f"| {'n/a' if r2 is None else f'${r2['profit_usd']:+.2f}'} | {r['wallet'][:10]} |"
        )
    won = sum(1 for r in fast if r["result"] == "won")
    lost = sum(1 for r in fast if r["result"] == "lost")
    void = sum(r["profit_usd"] for r in fast if r["result"] not in ("won", "lost"))
    out += [
        "",
        f"**Total: {len(fast)} bets. Record (30 s, voids left out): {won}-{lost}, "
        f"plus {len(fast) - won - lost} voids worth ${void:+.2f}. Fees ${fees:.2f}. "
        f"Profit after fees ${tot:+.2f} (30 s) and ${tot2:+.2f} (2 min); "
        f"before fees ${tot + fees:+.2f} (30 s).**",
        "",
    ]
    return out


def write_table(rows: list[dict], watch_rows: list[dict]) -> None:
    out = [
        "# Tennis paper bets",
        "",
        "$5 per bet, international Polymarket prices. The fee is paid on top of the $5, "
        "so a losing bet costs $5 plus the fee. One bet per pick; markets where list "
        "wallets backed both sides are skipped. Times are US Eastern. The last "
        "profit column is the same bet copied 2 minutes late instead of 30 seconds.",
        "",
        "## Whole list (249 wallets)",
        "",
        *table(rows),
        "## Watch group on its own",
        "",
        "Only the watch-group wallets (watch-wallets.txt), same rules, counted separately.",
        "",
        *table(watch_rows),
    ]
    (HERE / "paper-bets.md").write_text("\n".join(out))


def run(cache: HistoryCache, wallets: set[str]) -> tuple[int, int, list[dict], dict]:
    bets: dict[float, list[tuple[str, str, float, float]]] = {d: [] for d in DELAYS}
    matches = 0
    rows: list[dict] = []
    skipped = 0
    for eid in cache.event_ids():
        event = cache.load_event(eid)
        start = parse_ts(event.get("startTime"))
        if start is None or start < FROZEN_AT:
            continue
        matches += 1
        fills = sorted(cache.load_fills(eid), key=lambda f: f[0])
        markets = parse_markets(event)
        paths = price_paths(fills)
        markets = tennis_cutoffs(markets, paths)
        first: dict[tuple[str, str], tuple[float, int, float]] = {}
        for ts, wallet, cid, oi, side, price, _size, _taker in fills:
            m = markets.get(cid)
            if wallet not in wallets or m is None or ts >= m.kickoff:
                continue
            if (wallet, cid) not in first:
                k = oi if side == "BUY" else 1 - oi
                first[(wallet, cid)] = (ts, k, price if side == "BUY" else 1 - price)
        picks: dict[tuple[str, int], tuple[float, str, float]] = {}
        for (wallet, cid), (ts, k, wallet_q) in first.items():
            if (cid, k) not in picks or ts < picks[(cid, k)][0]:
                picks[(cid, k)] = (ts, wallet, wallet_q)
        backed = defaultdict(set)
        for cid, k in picks:
            backed[cid].add(k)
        for (cid, k), (ts, wallet, wallet_q) in picks.items():
            if len(backed[cid]) > 1:
                skipped += 1
                continue
            m = markets[cid]
            for d in DELAYS:
                p0 = paths[cid].price_after(ts + d, m.kickoff) if cid in paths else None
                if p0 is None:
                    continue
                q = p0 if k == 0 else 1 - p0
                if not PRICE_FLOOR <= q <= PRICE_CAP:
                    continue
                shares = UNIT / q
                fee = follower_fee(m, shares, q)
                pnl = shares * m.payout[k] - UNIT - fee
                bets[d].append((wallet, event.get("title") or "", m.payout[k], pnl))
                rows.append({
                    "delay_s": int(d), "match_start_utc": event.get("startTime"),
                    "match": event.get("title") or "", "market": m.kind.lower(),
                    "pick": outcome_name(event, cid, k), "wallet": wallet,
                    "wallet_price": round(wallet_q, 4), "copy_price": round(q, 4),
                    "fee": round(fee, 4), "result": result_word(m.payout[k]),
                    "profit_usd": round(pnl, 2),
                    # For orderbook/book_check.py (Will, 5 Nov): what the book offered then.
                    "cid": cid, "k": k, "wallet_ts": ts, "copy_ts": ts + d,
                    "fee_rate": m.fee_rate, "fee_exp": m.fee_exponent, "payout": m.payout[k],
                })  # fmt: skip
    return matches, skipped, rows, bets


def summary(label: str, matches: int, skipped: int, bets: dict) -> None:
    print(f"== {label}")
    print(f"Matches since the list was frozen: {matches}")
    print(f"Picks skipped because list wallets backed both sides: {skipped}")
    for d in DELAYS:
        b = bets[d]
        won = sum(1 for x in b if x[2] == 1.0)
        lost = sum(1 for x in b if x[2] == 0.0)
        push = len(b) - won - lost
        pnl = sum(x[3] for x in b)
        void = sum(x[3] for x in b if x[2] not in (0.0, 1.0))
        roi = pnl / (UNIT * len(b)) if b else 0.0
        rate = f"{won / (won + lost):.0%} won" if won + lost else "no decided bets"
        print(
            f"Copy {d:.0f} s late: {len(b)} bets. Record {won}-{lost} ({rate}), voids left out; "
            f"{push} voids (settled 50-50) worth ${void:+.2f}. Total {pnl / UNIT:+.2f} units "
            f"(${pnl:+.2f}), ROI after fees {roi:+.1%}, voids included"
        )
        # Will, 4 Nov: also show the total without single wins over $20, which come
        # from thin-market prices a real copy may not have got.
        big = [x for x in b if x[3] > BIG_WIN]
        rest = [x for x in b if x[3] <= BIG_WIN]
        rest_pnl = sum(x[3] for x in rest)
        rest_roi = rest_pnl / (UNIT * len(rest)) if rest else 0.0
        print(
            f"  Without single wins over ${BIG_WIN:.0f} ({len(big)} left out, worth "
            f"${sum(x[3] for x in big):+.2f}): {len(rest)} bets, ${rest_pnl:+.2f}, ROI {rest_roi:+.1%}"
        )


def order(rows: list[dict]) -> None:
    rows.sort(key=lambda r: (r["delay_s"], r["match_start_utc"] or "", r["match"]))


def main(data_dir: str) -> None:
    wallets = {r["wallet"] for r in csv.DictReader(open(HERE / "frozen-list-2026-10-29.csv"))}
    cache = HistoryCache(Path(data_dir))
    matches, skipped, rows, bets = run(cache, wallets)
    w_matches, w_skipped, w_rows, w_bets = run(cache, WATCH)
    order(rows)
    order(w_rows)
    (HERE / "bets-full.json").write_text(json.dumps({"list": rows, "top3": w_rows}))
    with open(HERE / "paper-bets.csv", "w", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["group", *(list(rows[0])[:11] if rows else ["delay_s"])],
            extrasaction="ignore",
        )
        w.writeheader()
        w.writerows({"group": "list", **r} for r in rows)
        w.writerows({"group": "top3", **r} for r in w_rows)
    write_table(rows, w_rows)
    summary("Whole list", matches, skipped, bets)
    summary("Watch group", w_matches, w_skipped, w_bets)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/paper-tennis")
