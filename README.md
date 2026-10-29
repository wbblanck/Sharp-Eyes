# Sharp-Eyes

Sharp bettor discovery and cross-venue copy-trading research platform: find
Polymarket traders with repeatable skill in a specific sport and bet type,
detect their new wagers, and paper-trade the same contract at the best price
on Polymarket US, Kalshi or Novig. **Paper mode only**: live order submission
is disabled in code (`src/sharp_eyes/safety.py`).

## Status

* **Phase 0, data capture (running):** an always-on worker records NFL
  catalogs, order books and trades on all four venues, and measures Polymarket
  Data API detection latency. See [docs/phase0-capture.md](docs/phase0-capture.md).
* **Phase 1, copyability (in review):** reviewed settlement templates for
  every core NFL market type on all four venues, a cross-venue matcher, and
  `sharp-eyes copyability-report`, which re-prices each Polymarket wager at
  what a follower could have bought after the delay, with fees, and scores it
  against the close. See [docs/phase1-copyability.md](docs/phase1-copyability.md).
  The canonical schema under `src/sharp_eyes/db` still has no migrations.
* **Sharp-trader history (no server):** `sharp-eyes history-fetch` downloads
  every settled NFL game and its fills from the public APIs into
  `data/history`, and `sharp-eyes sharp-report` ranks wallets by how often
  their bets beat the closing line, with significance, a luck correction and
  an out-of-sample check. Runs on a laptop, no database. See
  [docs/sharp-history.md](docs/sharp-history.md).

## Quick start (local)

```bash
uv sync
cp .env.example .env        # point SHARP_EYES_DATABASE_URL at a PostgreSQL 16
uv run sharp-eyes migrate
uv run sharp-eyes capture   # Ctrl-C to stop
uv run sharp-eyes status
```

Or everything in Docker: `docker compose up -d --build` (set
`POSTGRES_PASSWORD` in `.env`). Free hosting:
[docs/deploy-oracle-free.md](docs/deploy-oracle-free.md).

## Development

```bash
uv run ruff format src tests migrations && uv run ruff check src tests migrations
uv run mypy
SHARP_EYES_TEST_DATABASE_URL=postgresql+psycopg://...  uv run pytest   # DB tests skip without it
```
