# Phase 0: NFL data capture

The capture worker records what four venues show for NFL games, starting now,
because no venue sells historical order-book depth. Realistic backtests of
copying (what could a follower actually have bought, at what price and size,
seconds after a sharp traded?) can only cover periods we recorded ourselves.

It also measures how quickly Polymarket's Data API v2 exposes a fill after it
happens, which decides whether a 30-second signal limit is achievable.

## What is captured

| Venue | Role | Catalog | Order books | Trades |
|---|---|---|---|---|
| Polymarket (international) | Signal source | Gamma, NFL series 12185 | CLOB `POST /books`, 500 tokens per request; every non-prop game market | Live-data websocket (`activity`/`trades`, pushed as they happen) for catalog markets, plus Data API `/v2/trades` by event (maker and taker fills, polled every 2 s) to fill its gaps, plus a one-time full-history backfill per event |
| Polymarket US | Execution | Gateway `/v2/leagues/nfl/events`, then `/v1/events/{id}` | Gateway `/v1/markets/{slug}/book`; full-game moneyline, spread, total | None public. The tape needs an authenticated websocket (API key). Each book row keeps the gateway's market stats (last trade price, size and time, shares traded) |
| Kalshi | Execution | `/events` for KXNFLGAME, KXNFLSPREAD, KXNFLTOTAL, KXNFLTEAMTOTAL | `/markets/orderbooks`, 100 tickers per request | Global `/markets/trades` tape since the last checkpoint, filtered to those series |
| Novig | Execution | `/v3/public/catalog/events` and `/markets` (MONEY, SPREAD, TOTAL, TEAM_TOTAL, SPREAD_1H, TOTAL_1H) | `/v3/public/catalog/markets/{id}/book`, 20 levels, ETag-cached | `/v3/public/catalog/markets/{id}/trades` for markets whose catalog volume moved |

Games are captured from eight days before kickoff until six hours after.
Book polling speeds up as kickoff approaches (`config/default.yaml`,
`capture.tiers`): every 10 minutes when far out, every minute inside 36 hours,
every 15 seconds inside 3 hours and during play. A book is stored only when its
content changed since the last stored snapshot of that book.

## Units and conventions

* Prices are probabilities in [0, 1].
* Sizes count **$1-payout contracts** on every venue. A Novig contract pays
  1 cent, so Novig quantities are divided by 100.
* Book levels are best first: bids descending, asks ascending.
* Kalshi and Novig only publish buy orders. A Kalshi yes ask at p is a no bid at
  1 - p; a Novig ask on one outcome at p is a bid on the other outcome at 1 - p.
  Both are stored already converted into asks.
* `observed_at` is when our response arrived, in UTC. A backtest must use it,
  not a venue timestamp, to avoid look-ahead. Venue times are kept alongside
  (`ts` for trades, `venue_ts` for books where the venue sends one).
* `bet_type` x `period` is a coarse first classification per venue market type
  (audit recommendation 7). Settlement templates come in Phase 1.

## Tables (schema `capture`)

| Table | Contents |
|---|---|
| `events`, `markets` | Latest catalog record per venue object, with the raw payload |
| `catalog_versions` | Append-only history whenever an object's stable content changed (status, line, rules), prices and volumes excluded |
| `book_snapshots` | One row per changed book: levels as JSON, best bid and ask, venue sequence or time where available |
| `trades` | Deduplicated fills. Polymarket rows carry the wallet, the transaction hash, whether the fill also appeared in the taker-only feed, and latency bounds |
| `poll_runs` | Every poll: venue, job, start and end, success, request and item counts. Gaps here are gaps in coverage |
| `checkpoints` | Resume points (Kalshi tape watermark, Novig per-market trade cursors, Polymarket backfill markers) |
| `api_status_samples` | Polymarket `/v2/status` samples (the API's own serving lag) every 10 s |

A book is unchanged between two of its rows only if `poll_runs` shows that
venue's book job running throughout. Treat a gap in `poll_runs` as missing data.

## Known limits

* **Polymarket trade identity.** Neither feed has a trade id. The key is
  transaction hash + token + wallet + side + price + size (numbers in canonical
  form, so the websocket's `200` and the Data API's `200.0` match), with an
  ordinal for identical rows in one response (or, on the websocket, within 15
  minutes). Two genuinely identical fills that arrive in different polls would
  merge; this has not been observed. Each row keeps the first sighting per feed
  (`api_observed_at`, `ws_observed_at`); `observed_at` is the earlier of the two.
* **Polymarket maker or taker.** `seen_in_taker_feed` is true when the fill
  also appears with `taker_only=true`. Rows only in the full feed are maker
  fills, except when a taker row arrived between the two passes (rare; it is
  marked on the next poll).
* **Kalshi kickoff times** are estimated as expected expiration minus three
  hours (Kalshi game events have no start field). They are only used to pick
  the polling tier.
* **Novig's public routes share a per-IP throttle.** The worker runs Novig at
  2 requests per second, nearest games first. Older Novig fills are in its
  daily CSVs at data.novig.com (not yet ingested). A free Novig API key would
  raise the limit to 16 reads per second.
* **Polymarket US has no public tape.** Book rows keep last-trade stats, which
  show that trading happened but not every fill.
* **Polymarket fills can surface late.** In the first test run some fills
  appeared in `/v2/trades` about 100 to 120 seconds after their block time, while
  `/v2/status` reported only 2 to 4 seconds of lag. Each poll therefore re-reads
  the last 10 minutes (`trade_overlap_seconds`). See
  `docs/reports/2026-10-24-polymarket-latency.md`.
* **The websocket is new and not yet measured.** The worker subscribes to
  Polymarket's live-data websocket (`wss://ws-live-data.polymarket.com`,
  `activity`/`trades`, unfiltered, about one message per fill on all of
  Polymarket) and keeps fills in catalog markets. It reconnects with backoff and
  treats a minute of silence as a stall. Each connected minute is an `rtds` row
  in `poll_runs`, and a drop is a failed row. Still unverified: whether it
  carries maker fills (the poll keeps them either way), and whether every
  message has a transaction hash (fills without one are left to the poll). The
  `latency-report` coverage line answers both. Set `capture.polymarket.rtds:
  false` to turn it off.
* **Kalshi trades poll can hit 429.** The global tape is rate-limited per IP;
  a failed poll is retried next cycle from the same checkpoint, so nothing is
  lost.
* Backfilled Polymarket history is trader-price evidence only. It says what
  wallets paid, not what a follower could have paid.

## Commands

```bash
sharp-eyes migrate                    # create or upgrade the capture schema
sharp-eyes capture                    # run the worker (Ctrl-C or SIGTERM to stop)
sharp-eyes status --hours 1           # row counts and recent polls per venue
sharp-eyes health --max-age 900       # exit 1 if a venue stopped polling
sharp-eyes latency-report --hours 24 --out latency.md
sharp-eyes rtds-tail --seconds 30 --slug nfl-   # print websocket fills (connectivity check)
```

## Detection latency method

The Polymarket trades poll runs every 2 seconds per group of up to 20 events.
For a fill first returned by poll *k*, poll *k-1* (which covered the same
event) did not return it. So it became visible in the API between the start of
poll *k-1* and the arrival of poll *k*:

```
lower bound = prev_poll_at - block time
upper bound = observed_at  - block time
```

The upper bound is what a copy signal would experience with this setup. The
lower bound shows how much is the API rather than our polling. Block times are
whole seconds, so both carry up to one second of rounding. Backfilled rows and
the first poll of each event carry no bounds and are excluded. These use
`api_observed_at`, so the poll is still measured on its own when the websocket
saw a fill first.

For the websocket, latency is `ws_observed_at - block time`. Fills seen by both
feeds are compared head to head (`api_observed_at - ws_observed_at`), and
coverage counts fills seen by both, by the socket only and by the poll only
(split into taker and maker), over block times inside minutes the socket was
connected.
