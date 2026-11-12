# Sharp tennis traders on Polymarket: what we found (2026-10-29)

**Short answer: tennis has genuinely skilled bettors whose skill holds up over time, but none of it survives copying once the taker fee is paid. On international Polymarket that fee averaged 2.1% of each copied dollar in this data. Polymarket US fees for tennis were not checked.**

What was checked: every trade in the 10,662 ATP and WTA matches with at least $50k traded, from October 2025 to 28 October 2026 (32.5 million trades, 146,000 wallets). Bets placed before the match and bets placed during play were scored separately. To test whether a wallet's record is skill or luck, wallets were picked on matches up to 3 July 2026 and then checked on the 5,390 matches after that date, which they could not have known about.

## 1. Before the match (the skill test)

* 2,600 wallets bet in at least 20 matches with $5k or more before the start. **56 pass the skill test**: they regularly get better prices than where the market ends up just before the match, by more than luck allows even after correcting for testing thousands of wallets.
* **The skill is real.** Wallets flagged in the first half kept beating the final price by about 9% in the second half. Wallets that looked bad stayed bad.
* **But it can't be copied.** They get that edge by grabbing prices in the first moments. A copier buying the same thing later keeps only a small part of it:

| You copy after | Edge left before fees | After Polymarket's taker fee |
|---|---:|---:|
| 10 seconds | +1.1% | **-1.4%** |
| 30 seconds | +1.2% | **-1.3%** |
| 2 minutes | +0.4% | **-2.1%** |

  Measured on the final result rather than the closing price, copying them after 2 minutes made **0.0%** after fees in the second half of the year.
* Many of the top names bet on thousands of matches with small stakes, or fill mostly with resting orders. Whether they are bots was not checked.

## 2. Your "winning record" list (profitable, won more than 60%, 20+ matches, $5k+ before the match)

* 403 wallets qualify. This rule worked better in tennis than in NFL: the wallets it picked in the first half still made **+3.9%** in the second half (everyone else: -1.0%). That is unlikely to be pure luck.
* For a copier it is much thinner: **about +1% after fees**, and that is too small and noisy to tell apart from zero. Five wallets carry over half the money, and only 62 of 101 that stayed active were still profitable.

## 3. During play

* In-play is where most of the money is ($1.2 billion staked in the second half alone). **112 wallets pass an in-play skill test**: the price moves their way within five minutes of their bets. This is the strongest and most persistent signal in the data, and several of them made over $150k, up to $570k.
* Why they win was not checked. What the data shows is that **the edge is gone within 10 seconds**. Copying the flagged in-play wallets in the second half lost **1.2% after fees with a 10-second delay** and **2.1% with a 2-minute delay**.

## What this means

Copying tennis traders on Polymarket does not look profitable from history: the fee is bigger than the edge left over. Your winning-record list before the match came out around +1% for a copier after taker fees, which is not distinguishable from zero. Limit orders pay no fee on these markets (the fee schedule is taker-only), but whether limit orders would get filled was not tested.

Caveats: prices come from the trade record (Polymarket keeps no order-book history), and match start times are Polymarket's listed times, with a guard for matches that start early. ITF and doubles matches were left out (tiny markets).

The full tables follow; every ranked wallet is in the CSV.

---

# Sharp tennis traders on Polymarket

Matches 2025-10-08 to 2026-10-28: 10,662 settled tennis matches, 32,542,613 fills, 145,980 wallets. Ranked: 2,600 wallets with aggressive (taker) bets before the match starts in at least 20 matches and $5k staked pre-match.

* **Flagged sharp** (their taker bets beat the closing line, false-discovery rate under 5%): 56
* **Still worth copying** after a 120 s delay (sharp, and the delayed price still beats the close with t >= 2): 34
* **Winning record** (profitable pre-match and won more than 60% of bets, same match and stake floors): 403
* **In-play sharp** (price moves their way in the 5 minutes after their in-play taker bets, false-discovery rate under 5%, of 6,105 wallets with 20+ matches and $5k in-play): 112, of which 14 keep the edge with a 120 s delay

Columns: **Taker CLV** is the average edge of the wallet's aggressive pre-match bets versus the closing price, per dollar staked (+2% means they bought 2% cheaper than the close); the rank uses its t-statistic. **All CLV** adds their resting limit orders, which pick up half the spread for free. **ROI** is the settled pre-match result after taker fees. **Copy CLV** is the CLV a follower would get buying 120 s later, on all of the wallet's pre-match fills; **after fees** subtracts the follower's taker fee. t is the t-statistic, clustered by match; about 3 or more is unlikely to be luck. **Maker** is the share of stake filled as resting limit orders. **Live P&L** is the in-play result in dollars.

## Does it persist? Ranked on matches before 2026-07-03, measured after

Ranking used 5,272 matches; the check uses the 5,390 matches after. Rank correlation between earlier CLV t and later taker CLV, over 674 wallets active in both: **0.24**.

| Group | Wallets active after | Stake after | Taker CLV after | All CLV after | ROI after | Win rate after | Copy CLV after | Copy after fees |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Flagged sharp before split (q < 0.05, 33 wallets) | 18 | $1.8M | +9.4% | +3.8% | +5.5% | 51% | +0.4% | -2.1% |
| Top 25 before split | 13 | $1.2M | +13.0% | +5.5% | +7.2% | 50% | +0.7% | -1.7% |
| Bottom 25 before split | 12 | $838k | +0.4% | +0.9% | -10.7% | 46% | -0.9% | -3.8% |
| Winning record before split (ROI > 0, wins > 60%, 266 wallets) | 122 | $10.9M | +3.9% | +1.6% | +3.9% | 59% | +0.5% | -1.6% |
| Every wallet | 32856 | $242.4M | -0.1% | +0.0% | -1.0% | 51% | +0.0% | -2.1% |

### In-play: ranked on markout before 2026-07-03, measured after

Rank correlation over 1398 wallets: **0.20**.

| Group | Wallets active after | In-play stake after | Markout after | Copy markout after | Copy after fees |
|---|---:|---:|---:|---:|---:|
| Flagged live-sharp before split (58 wallets) | 46 | $361.4M | +2.9% | -0.2% | -2.1% |
| Top 25 live before split | 20 | $334.8M | +2.9% | -0.2% | -2.1% |
| Bottom 25 live before split | 10 | $2.6M | -1.3% | +0.3% | -1.4% |
| Every wallet | 42593 | $1232.2M | +0.1% | +0.1% | -1.7% |

## Top 30 pre-match by taker CLV t-statistic

| # | Wallet | Matches | Pre-match stake | Taker CLV (t) | All CLV | ROI (t) | Copy CLV (t) | Copy after fees | Maker | Live P&L (matches) | Main bet type | Last match | Flag |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 0x147c2760 | 5514 | $66k | +0.6% (10.7) | +0.6% | +0.3% (0.4) | +0.4% (5.3) | -1.4% | 71% | -$0k (356) | moneyline 100% | 2026-10-28 | copyable |
| 2 | 0x67e65bd1 | 155 | $105k | +5.7% (8.5) | -3.8% | -1.6% (-0.8) | -7.2% (-1.3) | -7.2% | 68% | +$4k (24) | moneyline 76% | 2026-04-08 | sharp |
| 3 | 0x9ef1dcac | 1247 | $16k | +2.2% (7.5) | +2.3% | +2.7% (1.0) | +1.4% (4.4) | -0.0% | 5% | -$0k (98) | moneyline 100% | 2026-08-01 | copyable |
| 4 | 0xfbe49f06 | 1981 | $17k | +1.9% (7.1) | +1.9% | +1.0% (0.5) | +1.5% (5.1) | +0.0% | 1% | -$0k (47) | moneyline 78% | 2026-10-28 | copyable |
| 5 | 0x9663a1bc | 1045 | $44k | +3.5% (5.5) | +3.4% | +8.4% (1.6) | +2.1% (2.9) | +0.4% | 2% | -$1k (22) | moneyline 100% | 2026-10-28 | copyable |
| 6 | 0x8027640c | 536 | $12k | +2.8% (5.4) | +2.8% | -3.5% (-0.7) | +2.7% (4.8) | +1.4% | 1% | -$0k (39) | moneyline 100% | 2026-04-23 | copyable |
| 7 | 0x5e3040eb | 3767 | $1.3M | +1.2% (5.4) | +1.3% | +2.1% (1.3) | -0.0% (-0.2) | -1.3% | 86% | -$14k (1561) | moneyline 40% | 2026-10-28 | sharp |
| 8 | 0xf5fe759c | 206 | $1.7M | +23.3% (5.2) | +9.2% | +9.4% (6.4) | +1.7% (3.2) | +0.2% | 74% | +$103k (90) | moneyline 88% | 2026-10-26 | copyable |
| 9 | 0x8fe730b5 | 166 | $5k | +14.7% (5.2) | +14.7% | +10.3% (3.9) | +8.0% (1.7) | +5.9% | 3% | +$1k (425) | set handicap 46% | 2026-10-28 | sharp |
| 10 | 0x877fdb54 | 59 | $41k | +3.0% (5.2) | +2.9% | -4.6% (-0.3) | +3.1% (4.5) | +2.0% | 5% | +$0k (0) | moneyline 100% | 2026-09-01 | copyable |
| 11 | 0xeaac36f7 | 2143 | $916k | +1.7% (5.0) | +1.2% | +3.5% (1.3) | -0.1% (-0.4) | -2.2% | 64% | -$3k (79) | moneyline 97% | 2026-10-28 | sharp |
| 12 | 0x5213eb85 | 2106 | $1.0M | +1.7% (4.6) | +1.2% | +5.0% (2.0) | +0.1% (0.4) | -1.9% | 68% | +$2k (83) | moneyline 97% | 2026-10-28 | sharp |
| 13 | 0x01c78f88 | 4251 | $1.2M | +1.8% (4.5) | +1.3% | +12.1% (2.2) | -0.0% (-0.2) | -2.7% | 56% | -$8k (572) | moneyline 100% | 2026-10-28 | sharp |
| 14 | 0xbfdd2fb3 | 108 | $7k | +2.1% (4.5) | +1.2% | -10.5% (-0.4) | +1.5% (1.9) | -0.4% | 17% | +$1k (4) | moneyline 69% | 2026-10-25 | sharp |
| 15 | 0x65b9e20f | 44 | $409k | +1.5% (4.4) | +0.6% | -3.3% (-0.4) | -0.1% (-0.4) | -1.3% | 81% | -$19k (49) | moneyline 100% | 2026-05-04 | sharp |
| 16 | 0xbc088291 | 948 | $61k | +1.5% (4.4) | +1.5% | -11.6% (-2.9) | +0.7% (1.8) | -1.0% | 1% | -$0k (3) | moneyline 96% | 2026-09-16 | sharp |
| 17 | 0x3dcf59b8 | 336 | $53k | +1.6% (4.4) | +1.6% | +3.1% (0.6) | +1.4% (3.8) | +1.4% | 2% | +$1k (45) | moneyline 99% | 2026-03-30 | copyable |
| 18 | 0xe062f353 | 300 | $30k | +2.4% (4.4) | +2.4% | +0.6% (0.1) | +2.4% (3.3) | +0.8% | 1% | +$0k (3) | moneyline 82% | 2026-05-21 | copyable |
| 19 | 0x200ffb57 | 6310 | $797k | +1.3% (4.2) | +1.0% | +3.9% (2.9) | -0.1% (-0.9) | -1.9% | 93% | -$2k (179) | moneyline 65% | 2026-10-28 | sharp |
| 20 | 0x0b567742 | 438 | $9k | +2.1% (4.2) | +2.0% | -4.3% (-1.0) | +1.8% (3.9) | +0.1% | 2% | -$0k (26) | moneyline 100% | 2026-09-11 | copyable |
| 21 | 0xf26817d9 | 54 | $5k | +8.8% (4.2) | +8.8% | -13.2% (-1.0) | +7.2% (4.6) | +6.0% | 0% | -$0k (1) | moneyline 80% | 2026-06-19 | copyable |
| 22 | 0x6f2e5224 | 844 | $68k | +1.7% (4.1) | +1.7% | +3.3% (0.8) | +1.4% (3.2) | +0.2% | 7% | -$1k (539) | moneyline 99% | 2026-09-01 | copyable |
| 23 | 0x0d10fdbc | 1717 | $15k | +2.5% (4.0) | +2.5% | +2.3% (1.1) | +2.0% (2.5) | +0.3% | 0% | -$1k (3538) | moneyline 50% | 2026-10-28 | copyable |
| 24 | 0x6d3c5bd1 | 3288 | $10.4M | +1.0% (4.0) | +0.2% | -0.2% (-0.2) | -0.2% (-2.4) | -2.3% | 91% | +$34k (400) | moneyline 84% | 2026-10-28 | sharp |
| 25 | 0xa5901037 | 631 | $5k | +1.7% (3.9) | +1.7% | -5.7% (-1.5) | +0.7% (2.4) | -0.7% | 0% | -$0k (418) | moneyline 58% | 2026-05-12 | copyable |
| 26 | 0xf8831548 | 22 | $18.1M | +1.3% (3.9) | +1.3% | +21.0% (2.3) | +1.8% (4.4) | +1.1% | 5% | +$398k (12) | moneyline 100% | 2026-06-07 | copyable |
| 27 | 0xfded52bd | 24 | $22k | +2.6% (3.9) | +2.8% | -6.9% (-0.3) | +2.9% (3.6) | +2.1% | 35% | +$1k (2) | moneyline 100% | 2026-06-12 | copyable |
| 28 | 0x18895028 | 188 | $24k | +2.9% (3.8) | +3.1% | +5.0% (0.8) | +1.8% (3.4) | +1.8% | 41% | -$0k (26) | moneyline 100% | 2026-02-01 | copyable |
| 29 | 0x73afc816 | 58 | $1.2M | +17.6% (3.8) | +6.8% | +6.4% (6.2) | +0.6% (2.3) | -1.2% | 66% | +$87k (39) | moneyline 75% | 2026-07-22 | copyable |
| 30 | 0x2b9d225b | 84 | $7k | +3.7% (3.7) | +3.7% | +0.3% (0.0) | -0.6% (-0.5) | -3.0% | 0% | +$1k (218) | moneyline 59% | 2026-10-28 | sharp |

## Winning record: ROI above zero and over 60% of bets won

A bet is the wallet's net pre-match position in one market. Win rate ignores the price paid (backing 80c favourites wins 80% and can still lose money), so read it with ROI and CLV. Sorted by ROI t-statistic.

| # | Wallet | Matches | Bets | Win rate | Pre-match stake | ROI (t) | Taker CLV (t) | Copy CLV (t) | Copy after fees | Main bet type | Last match | Also CLV-sharp |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 0xb5b5632a | 41 | 41 | 63% | $9k | +139.3% (9.1) | -0.4% (-0.5) | +1.2% (2.3) | -0.7% | moneyline 100% | 2026-10-21 |  |
| 2 | 0xd0c7f0d4 | 37 | 37 | 78% | $7k | +12.0% (6.5) | -0.0% (-0.1) | -0.0% (-0.1) | -0.7% | moneyline 100% | 2026-10-28 |  |
| 3 | 0xf5fe759c | 206 | 367 | 90% | $1.7M | +9.4% (6.4) | +23.3% (5.2) | +1.7% (3.2) | +0.2% | moneyline 88% | 2026-10-26 | yes |
| 4 | 0x57b9589d | 28 | 30 | 63% | $9k | +2.0% (6.2) | -0.2% (-2.9) | -0.2% (-6.2) | -0.2% | moneyline 100% | 2026-05-05 |  |
| 5 | 0x73afc816 | 58 | 358 | 99% | $1.2M | +6.4% (6.2) | +17.6% (3.8) | +0.6% (2.3) | -1.2% | moneyline 75% | 2026-07-22 | yes |
| 6 | 0xc3e550fa | 28 | 28 | 96% | $42k | +5.7% (6.1) | -1.6% (-2.2) | -0.8% (-1.4) | -1.2% | moneyline 100% | 2026-10-08 |  |
| 7 | 0x88f17731 | 20 | 20 | 100% | $9k | +5.7% (5.8) | -0.6% (-1.2) | -0.6% (-0.8) | -0.7% | moneyline 100% | 2026-05-24 |  |
| 8 | 0x72e15978 | 69 | 194 | 88% | $190k | +1.3% (5.4) | +1.8% (0.8) | +0.8% (1.1) | -1.3% | moneyline 68% | 2026-10-26 |  |
| 9 | 0x09ad5862 | 23 | 27 | 81% | $44k | +27.8% (4.9) | -1.1% (-3.8) | -0.4% (-1.1) | -0.4% | moneyline 85% | 2026-06-20 |  |
| 10 | 0x007f5b6c | 34 | 34 | 94% | $8k | +9.6% (4.8) | -0.4% (-1.3) | -0.1% (-0.4) | -0.3% | moneyline 100% | 2026-06-03 |  |
| 11 | 0x67706ec3 | 84 | 84 | 62% | $14k | +43.1% (4.6) | +3.9% (1.6) | +4.2% (1.5) | +2.7% | moneyline 98% | 2026-10-06 |  |
| 12 | 0x3fe9b9d0 | 116 | 116 | 94% | $41k | +8.4% (4.3) | +22.9% (1.2) | -3.4% (-1.5) | -3.7% | completed match 100% | 2026-10-09 |  |
| 13 | 0xd8b4d1e5 | 42 | 327 | 95% | $822k | +8.4% (4.1) | +24.0% (3.4) | -0.0% (-0.0) | -2.5% | moneyline 81% | 2026-10-20 | yes |
| 14 | 0xe571312e | 112 | 112 | 96% | $40k | +6.7% (4.1) | -4.0% (-0.8) | +1.4% (0.6) | +1.0% | completed match 100% | 2026-10-09 |  |
| 15 | 0xe0f383ea | 114 | 114 | 94% | $38k | +7.1% (4.0) | +7.1% (1.2) | -6.5% (-2.4) | -6.8% | completed match 100% | 2026-10-09 |  |
| 16 | 0x211dcd07 | 74 | 74 | 66% | $23k | +32.4% (3.5) | -0.6% (-1.6) | +0.6% (1.2) | -0.2% | moneyline 76% | 2026-06-10 |  |
| 17 | 0x37cc45f5 | 137 | 137 | 94% | $45k | +8.2% (3.5) | +18.5% (0.9) | -5.4% (-3.3) | -5.7% | completed match 100% | 2026-10-09 |  |
| 18 | 0xf32de582 | 59 | 59 | 64% | $42k | +28.3% (3.4) | +0.1% (0.1) | +1.0% (1.4) | +0.6% | moneyline 98% | 2026-10-27 |  |
| 19 | 0xfc4191ae | 284 | 284 | 96% | $30k | +5.3% (3.4) | n/a (n/a) | -2.3% (-1.8) | -2.6% | completed match 100% | 2026-10-09 |  |
| 20 | 0x986b121c | 24 | 24 | 67% | $20k | +14.7% (3.4) | -0.4% (-15.2) | +1.4% (1.7) | +0.9% | moneyline 100% | 2026-10-13 |  |
| 21 | 0x8406252b | 22 | 22 | 73% | $28k | +16.7% (3.4) | +0.0% (0.1) | -0.2% (-0.4) | -0.2% | moneyline 98% | 2026-04-16 |  |
| 22 | 0x17cb6a89 | 34 | 34 | 88% | $117k | +7.5% (3.3) | -0.9% (-1.6) | -0.3% (-0.5) | -0.5% | moneyline 100% | 2026-10-12 |  |
| 23 | 0xa1f699a9 | 40 | 41 | 66% | $10k | +12.4% (3.3) | +0.7% (1.7) | +1.2% (3.5) | +0.3% | moneyline 100% | 2026-06-07 |  |
| 24 | 0xa1089452 | 30 | 30 | 77% | $23k | +13.1% (3.2) | +0.2% (0.4) | +0.6% (1.8) | -0.3% | moneyline 100% | 2026-10-28 |  |
| 25 | 0x29de877f | 33 | 33 | 64% | $12k | +51.8% (3.2) | -1.8% (-3.1) | -0.6% (-0.9) | -0.6% | moneyline 100% | 2026-02-15 |  |
| 26 | 0xc7f66468 | 253 | 253 | 96% | $26k | +5.8% (3.2) | n/a (n/a) | -0.8% (-0.7) | -1.1% | completed match 100% | 2026-10-09 |  |
| 27 | 0x09ec25a4 | 23 | 23 | 78% | $11k | +22.0% (3.2) | -1.5% (-1.2) | -0.9% (-0.7) | -0.9% | moneyline 100% | 2026-01-10 |  |
| 28 | 0x38723c33 | 125 | 125 | 92% | $46k | +6.3% (3.1) | +13.6% (1.2) | -0.8% (-0.3) | -1.1% | completed match 99% | 2026-10-09 |  |
| 29 | 0x7d267b9f | 80 | 80 | 74% | $14k | +11.0% (3.1) | -0.4% (-1.8) | +0.0% (0.0) | -0.1% | moneyline 100% | 2026-09-11 |  |
| 30 | 0x1e89b58b | 22 | 23 | 83% | $13k | +51.3% (3.1) | -0.4% (-1.2) | +0.3% (1.1) | -1.8% | moneyline 75% | 2026-10-13 |  |

## Top 30 in-play by markout t-statistic

**Markout** is how far the price moved in the bettor's favour 5 minutes after their in-play taker bets, per dollar. **Copy markout** is the same for a follower buying 120 s later. Live prices jump on every point, so only a big t means anything.

| # | Wallet | In-play matches | In-play stake | Markout (t) | Copy markout (t) | Copy after fees | Live P&L | Maker | Last match | Flag |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 0xde9f7f4e | 7945 | $29.7M | +4.7% (24.4) | -0.4% (-2.0) | -1.6% | +$569k | 14% | 2026-10-28 | sharp |
| 2 | 0x42c99f38 | 6568 | $18.8M | +5.3% (19.4) | -0.1% (-0.4) | -1.4% | +$505k | 27% | 2026-10-28 | sharp |
| 3 | 0xa509ae94 | 7868 | $3.7M | +2.1% (18.8) | +0.2% (2.0) | -0.7% | +$43k | 62% | 2026-10-28 | copyable |
| 4 | 0x60a32ad6 | 965 | $295k | +4.4% (17.5) | +0.4% (1.7) | -0.7% | +$10k | 0% | 2026-06-04 | sharp |
| 5 | 0x205b4e3a | 275 | $47k | +7.6% (17.0) | +10.4% (1.7) | +10.1% | +$4k | 0% | 2026-08-19 | sharp |
| 6 | 0xeea3f08e | 5532 | $14.6M | +2.8% (16.7) | -0.1% (-0.8) | -1.6% | +$155k | 0% | 2026-10-28 | sharp |
| 7 | 0x98db8cca | 7304 | $16.3M | +2.0% (14.6) | +0.1% (0.8) | -1.1% | +$203k | 56% | 2026-10-28 | sharp |
| 8 | 0x6485f47d | 4117 | $8.2M | +5.3% (14.0) | +0.0% (0.1) | -1.5% | +$221k | 20% | 2026-10-28 | sharp |
| 9 | 0x204f72f3 | 6229 | $57.9M | +2.2% (13.5) | -0.2% (-1.1) | -1.0% | +$556k | 17% | 2026-08-26 | sharp |
| 10 | 0x0f17aacb | 2803 | $3.0M | +4.7% (13.2) | +0.2% (0.5) | -1.6% | +$55k | 19% | 2026-10-28 | sharp |
| 11 | 0x85630920 | 209 | $18k | +7.2% (12.0) | +1.6% (0.7) | +1.2% | +$1k | 0% | 2026-10-28 | sharp |
| 12 | 0x4abdea21 | 1003 | $339k | +4.9% (10.4) | +0.2% (0.5) | -1.7% | +$10k | 0% | 2026-10-23 | sharp |
| 13 | 0xf0ea0711 | 1058 | $346k | +4.5% (9.5) | +0.4% (0.8) | -1.4% | +$8k | 0% | 2026-10-23 | sharp |
| 14 | 0x85583637 | 967 | $327k | +5.1% (9.4) | +0.4% (1.0) | -1.4% | +$11k | 0% | 2026-10-28 | sharp |
| 15 | 0xe839e7fe | 1120 | $344k | +5.6% (9.0) | -0.4% (-1.1) | -2.3% | +$14k | 0% | 2026-10-25 | sharp |
| 16 | 0x0f76e9a9 | 3838 | $1.9M | +2.0% (8.8) | +0.2% (1.1) | -1.4% | +$4k | 29% | 2026-10-28 | sharp |
| 17 | 0xb595d09c | 367 | $536k | +8.1% (8.2) | +5.6% (2.3) | +5.1% | +$43k | 1% | 2026-10-20 | copyable |
| 18 | 0xd32e92fd | 1056 | $345k | +4.6% (8.0) | -0.5% (-1.3) | -2.3% | +$11k | 0% | 2026-10-23 | sharp |
| 19 | 0xd2e82092 | 1007 | $335k | +4.9% (7.9) | -0.2% (-0.4) | -2.0% | +$11k | 0% | 2026-10-23 | sharp |
| 20 | 0xae5123e8 | 483 | $2.6M | +4.3% (7.8) | -0.4% (-0.7) | -1.8% | +$59k | 15% | 2026-10-28 | sharp |
| 21 | 0x821dab05 | 2778 | $15.7M | +2.5% (7.7) | +0.7% (2.4) | -0.7% | +$322k | 19% | 2026-10-28 | copyable |
| 22 | 0x88f9a9b2 | 1027 | $323k | +5.0% (7.4) | +0.6% (1.4) | -1.1% | +$8k | 0% | 2026-10-23 | sharp |
| 23 | 0xbb3eaeb8 | 1044 | $341k | +4.7% (7.4) | +0.1% (0.2) | -1.7% | +$9k | 0% | 2026-10-25 | sharp |
| 24 | 0x0d2d845a | 4014 | $34.3M | +4.8% (7.4) | +0.3% (0.4) | -1.4% | +$13k | 99% | 2026-10-28 | sharp |
| 25 | 0x31121402 | 191 | $14k | +8.4% (7.1) | +3.0% (0.6) | +2.4% | +$1k | 0% | 2026-10-28 | sharp |
| 26 | 0xa7761028 | 20 | $14k | +4.6% (6.8) | +4.1% (16.4) | +4.1% | +$1k | 89% | 2026-02-04 | copyable |
| 27 | 0xda179b2e | 21 | $12k | +8.2% (6.7) | +1.6% (2.0) | -0.3% | +$0k | 15% | 2026-10-16 | sharp |
| 28 | 0xab417c0b | 289 | $47k | +11.1% (6.5) | +4.1% (2.0) | +2.0% | -$0k | 74% | 2026-08-29 | copyable |
| 29 | 0x972bf37c | 1812 | $9.2M | +1.3% (6.4) | +0.2% (1.0) | -0.2% | +$60k | 65% | 2026-04-10 | sharp |
| 30 | 0x7ca56b03 | 48 | $6k | +7.2% (6.4) | +12.8% (1.6) | +11.1% | +$0k | 1% | 2026-06-26 | sharp |

## Caveats

* The close and the copy price come from the trade tape, not order books (Polymarket keeps no historical books), so they mix bid and ask prints. Thin alternate lines have noisy closes.
* Pre-match fills priced below 3c or above 97c, and fills after a market closed, are left out: they carry no information about skill.
* In-play bets have no closing line, so they do not affect the pre-match rank; they are scored on the price 5 minutes later instead.
* A wallet can be one person with several wallets, or a bot. Maker share near 100% usually means a market maker earning the spread, which is not copyable even when CLV is positive.
* Match start times are Polymarket's listed times. When the moneyline swings like live play in the hour before the listed start, the match is treated as started at that swing.
