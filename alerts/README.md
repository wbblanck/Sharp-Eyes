# Tennis pick alerts

Posts each new pre-match ATP/WTA pick made by the frozen tennis list to Discord,
with the sharp's price, their record, and the best price on Polymarket US, Kalshi
or Novig. Nothing is bought.

`.github/workflows/tennis-alerts.yml` runs `live_alerts.py` every 5 minutes until
2026-11-26 (GitHub can start scheduled runs late when it is busy). What was
already posted is kept in the Actions cache between runs.

## Two repository secrets (Settings > Secrets and variables > Actions)

* `DISCORD_WEBHOOK`: the Discord webhook link.
* `WALLET_LIST`: the frozen list as CSV text with the header
  `wallet,matches,win_rate,roi,pre_match_stake`. It is kept as a secret so the
  list stays out of this public repo.

Run by hand: Actions > Tennis alerts > Run workflow.
