# Finding sharp NFL traders from public history (no server)

Polymarket's international venue publishes every fill with the wallet behind
it, and Gamma keeps every settled market. That is enough to tell skill from
luck without any capture running: download the history once, score it
locally, and top it up after each NFL week. Nothing here needs PostgreSQL,
Docker or an always-on host; a laptop or a cloud sandbox is enough.

```bash
uv sync
uv run sharp-eyes history-fetch                 # ~450 games, ~15 min, ~1 GB in data/history
uv run sharp-eyes sharp-report --split 2026-08-01 \
    --out docs/reports/sharp-nfl.md --csv data/sharp-nfl.csv
```

`history-fetch` only downloads games it has not cached yet, so re-running it
after a week of games takes a minute. Seasons come from the Gamma series ids
in `history/fetch.py` (`SEASON_SERIES`); add the next season's id there.

## What gets measured

Every fill is turned into "bought outcome k at price q for s shares" (a sell
of one side at p is a buy of the other side at 1 - p). Fills priced under 3c
or over 97c, and fills after the market closed, are dropped. Each wallet then
gets, per game:

| Yardstick | Meaning | Why |
|---|---|---|
| **Taker CLV** | edge of the wallet's aggressive pre-game bets versus the closing price (volume-weighted over the last 15 minutes before kickoff), per dollar | The ranking key. Beating the close is the standard skill test in sports betting and is far less noisy than results. Taker fills pay the ask, so a spread-capturing market maker does not look sharp. |
| All CLV | the same, including resting limit orders | Shown, not ranked: a filled bid beats a mid-ish close by half the spread with no view on the game. |
| ROI | settled pre-game result after taker fees | The honest bottom line, but an NFL side is close to a coin flip, so it needs many games. |
| Copy CLV | CLV at the first price printed 120 s after the wager (`--copy-delay`) | What a follower detecting the trade late would have got. Phase 0 measured Data API detection at p50 13 s, p90 108 s. |
| Live P&L | in-game result in dollars | In-game bets have no closing line, so they do not affect the rank. |

Each ratio has a t-statistic clustered by game (one wallet's fills on one game
are not independent). With thousands of wallets, some reach t = 3 by luck, so
the one-sided p-values get a Benjamini-Hochberg correction; **sharp** means
q < 0.05 with positive taker CLV, and **copyable** means sharp with copy CLV
t >= 2.

The persistence check (`--split`) ranks wallets on games before the split
date and measures the same wallets on the games after. Luck does not carry
over; skill does.

## Limits

* The close and the copy price are read off the trade tape: Polymarket keeps
  no historical order books, so prints mix bids and asks. Thin alternate
  lines have noisy closes.
* Wallet is not person: one bettor can use several wallets.
* Only international Polymarket attributes trades, and US persons cannot
  open positions there, so this finds whom to follow; execution stays on
  Polymarket US, Kalshi or Novig (Phase 1 copyability).
