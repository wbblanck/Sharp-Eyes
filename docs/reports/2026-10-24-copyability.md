# Copyability of Polymarket NFL wagers

Window: 2026-10-21T17:29:26+00:00 to 2026-10-24T17:29:26+00:00 (UTC, block time). Matcher nfl-core-1, settlement templates 2026.10.24.

Each wager is a wallet's run of BUY fills on one outcome. A follower acts 5.0 s after we first saw it, buying $10.00 on Polymarket US, Kalshi or Novig at the best fee-inclusive price in the captured book. Pre-game NFL moneyline, spread and total only. Prices in cents per $1 contract.

* Live-detected fills: 68 (backfilled fills excluded: 6,041)
* Wagers: 48; at least $100 notional: 15
* Outcome: SCORED 15

## Scored wagers

| measure | n | mean | median | share > 0 |
|---|---|---|---|---|
| slippage | 15 | +0.41 | +0.75 | 73% |
| slippage_with_fees | 15 | +2.13 | +2.47 | 100% |
| follower_clv | 0 | n/a | n/a | n/a |
| trader_clv | 0 | n/a | n/a | n/a |
| copy_cost | 0 | n/a | n/a | n/a |

slippage = follower average price minus trader price; slippage_with_fees adds the follower's taker fee per contract; follower_clv = closing mid minus follower price with fees; trader_clv = Polymarket closing mid minus trader price; copy_cost = trader_clv minus follower_clv.

Best venue: POLYMARKET_US 14, KALSHI 1

Match state of the chosen contract: EQUIVALENT_WITH_RULE_DIFFERENCE 15

Quote staleness bound (capture tier interval): 60 s: 15

Detection delay (first fill block time to first observation): median 24 s, p90 173 s.

## Wallets with the most scored wagers

| wallet | scored | mean follower CLV | mean trader CLV | mean slippage |
|---|---|---|---|---|
| `0xeed8c2be411025120fb511ea2332dd0a1f6135f0` | 2 | n/a | n/a | -0.26 |
| `0x0d2d845a6ff64e31e04a70afce8a573940767ff5` | 1 | n/a | n/a | +0.75 |
| `0x1f3a646ce5cbe2c70270e7a46161d89b7c7b895d` | 1 | n/a | n/a | +0.75 |
| `0x2d6ac4f70307102ac46e9e6ded67f3838ddf8add` | 1 | n/a | n/a | +0.75 |
| `0x54ce7dd357766fc3255645e55ef41edd51cc9f80` | 1 | n/a | n/a | -0.50 |
| `0x73e83485b8e20b70c53c27bef8ba4c62575dcd6f` | 1 | n/a | n/a | -1.50 |
| `0x796fc6fda8f8e03c03e2a2d012155989960300f6` | 1 | n/a | n/a | +0.75 |
| `0x9703676286b93c2eca71ca96e8757104519a69c2` | 1 | n/a | n/a | +0.75 |
| `0xcf7379b4b891c06d88807f6f70efa75378120215` | 1 | n/a | n/a | +1.18 |
| `0xdc41c39b95453c943174f369926018f6963bdd7e` | 1 | n/a | n/a | +0.00 |
| `0xe963d57ab09233f3cb2bf1546660a1b4638e6753` | 1 | n/a | n/a | +1.75 |
| `0xefde78f38169634477f6ff46572128b6d21a6505` | 1 | n/a | n/a | +0.75 |
| `0xf1ef8705e9f63c790c6fffd6329aea7011718cd6` | 1 | n/a | n/a | +0.75 |
| `0xf7f0b0b1e9c0fe02ccad926916ee31aef74b912c` | 1 | n/a | n/a | +0.50 |

A handful of wagers says nothing about skill; this table is for spotting wallets worth studying, not for qualification.

## Catalog coverage

Buy options per venue: POLYMARKET_US 1,988, POLYMARKET 1,568, NOVIG 1,488, KALSHI 1,296
