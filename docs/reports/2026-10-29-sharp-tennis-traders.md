# Sharp tennis traders on Polymarket: what we found (2026-10-29)

**Short answer: tennis has more genuinely skilled bettors than NFL, and their skill holds up over time, but none of it survives copying once Polymarket's taker fee (about 2c per dollar) is paid. Tennis looks worse for copying than NFL did.**

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
* Many of the top names are bots: thousands of matches, small stakes, or mostly resting orders.

## 2. Your "winning record" list (profitable, won more than 60%, 20+ matches, $5k+ before the match)

* 403 wallets qualify. This rule worked better in tennis than in NFL: the wallets it picked in the first half still made **+3.9%** in the second half (everyone else: -1.0%). That is unlikely to be pure luck.
* For a copier it is much thinner: **about +1% after fees**, and that is too small and noisy to tell apart from zero. Five wallets carry over half the money, and only 62 of 101 that stayed active were still profitable.

## 3. During play

* In-play is where most of the money is ($1.2 billion staked in the second half alone). **112 wallets pass an in-play skill test**: the price moves their way within five minutes of their bets. This is the strongest and most persistent signal in the data, and several of them made over $150k, up to $570k.
* It is speed, not judgment: people with a faster score feed or someone at the court. **It is gone within seconds.** Copying the flagged in-play wallets in the second half lost **1.2% after fees with a 10-second delay** and **2.1% with a 2-minute delay**.

## What this means

Copying tennis traders on Polymarket does not look profitable from history: the fee is bigger than the edge left over. The only thin possibility is your winning-record list before the match, placed as limit orders so you pay no taker fee, but the expected gain is around 1% and not proven.

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
| 1 | [0x147c2760](https://polymarket.com/profile/0x147c2760baa011fdcd0d02ea0f610ffb0fd92540) | 5514 | $66k | +0.6% (10.7) | +0.6% | +0.3% (0.4) | +0.4% (5.3) | -1.4% | 71% | -$0k (356) | moneyline 100% | 2026-10-28 | copyable |
| 2 | [0x67e65bd1](https://polymarket.com/profile/0x67e65bd160df9306af70f0f4d211b2308e6686ed) | 155 | $105k | +5.7% (8.5) | -3.8% | -1.6% (-0.8) | -7.2% (-1.3) | -7.2% | 68% | +$4k (24) | moneyline 76% | 2026-04-08 | sharp |
| 3 | [0x9ef1dcac](https://polymarket.com/profile/0x9ef1dcac29e39d2279c2c393a532739c11145aca) | 1247 | $16k | +2.2% (7.5) | +2.3% | +2.7% (1.0) | +1.4% (4.4) | -0.0% | 5% | -$0k (98) | moneyline 100% | 2026-08-01 | copyable |
| 4 | [0xfbe49f06](https://polymarket.com/profile/0xfbe49f06348d605b47ec2d681569f479c8c8f12f) | 1981 | $17k | +1.9% (7.1) | +1.9% | +1.0% (0.5) | +1.5% (5.1) | +0.0% | 1% | -$0k (47) | moneyline 78% | 2026-10-28 | copyable |
| 5 | [0x9663a1bc](https://polymarket.com/profile/0x9663a1bc594a019693631f39ed50e03496185b70) | 1045 | $44k | +3.5% (5.5) | +3.4% | +8.4% (1.6) | +2.1% (2.9) | +0.4% | 2% | -$1k (22) | moneyline 100% | 2026-10-28 | copyable |
| 6 | [0x8027640c](https://polymarket.com/profile/0x8027640c514744af10ffd2e3459fb9ada639cf81) | 536 | $12k | +2.8% (5.4) | +2.8% | -3.5% (-0.7) | +2.7% (4.8) | +1.4% | 1% | -$0k (39) | moneyline 100% | 2026-04-23 | copyable |
| 7 | [0x5e3040eb](https://polymarket.com/profile/0x5e3040eb55cb0f4f86eb0af40cb84c9d3585acbf) | 3767 | $1.3M | +1.2% (5.4) | +1.3% | +2.1% (1.3) | -0.0% (-0.2) | -1.3% | 86% | -$14k (1561) | moneyline 40% | 2026-10-28 | sharp |
| 8 | [0xf5fe759c](https://polymarket.com/profile/0xf5fe759cece500f58a431ef8dacea321f6e3e23d) | 206 | $1.7M | +23.3% (5.2) | +9.2% | +9.4% (6.4) | +1.7% (3.2) | +0.2% | 74% | +$103k (90) | moneyline 88% | 2026-10-26 | copyable |
| 9 | [0x8fe730b5](https://polymarket.com/profile/0x8fe730b55cf3468c01a884cfcde79c2dfb4d6c1f) | 166 | $5k | +14.7% (5.2) | +14.7% | +10.3% (3.9) | +8.0% (1.7) | +5.9% | 3% | +$1k (425) | set handicap 46% | 2026-10-28 | sharp |
| 10 | [0x877fdb54](https://polymarket.com/profile/0x877fdb546da48353fd712056495f66e31dad8f3b) | 59 | $41k | +3.0% (5.2) | +2.9% | -4.6% (-0.3) | +3.1% (4.5) | +2.0% | 5% | +$0k (0) | moneyline 100% | 2026-09-01 | copyable |
| 11 | [0xeaac36f7](https://polymarket.com/profile/0xeaac36f714563e13d88db7a4f0a0898388f2d71d) | 2143 | $916k | +1.7% (5.0) | +1.2% | +3.5% (1.3) | -0.1% (-0.4) | -2.2% | 64% | -$3k (79) | moneyline 97% | 2026-10-28 | sharp |
| 12 | [0x5213eb85](https://polymarket.com/profile/0x5213eb85fcd465c8927a8382f95dd2dc22306a35) | 2106 | $1.0M | +1.7% (4.6) | +1.2% | +5.0% (2.0) | +0.1% (0.4) | -1.9% | 68% | +$2k (83) | moneyline 97% | 2026-10-28 | sharp |
| 13 | [0x01c78f88](https://polymarket.com/profile/0x01c78f8873c0c86d6b6b92ff627e3802237ee995) | 4251 | $1.2M | +1.8% (4.5) | +1.3% | +12.1% (2.2) | -0.0% (-0.2) | -2.7% | 56% | -$8k (572) | moneyline 100% | 2026-10-28 | sharp |
| 14 | [0xbfdd2fb3](https://polymarket.com/profile/0xbfdd2fb3f69cd098b395eb7390fe973a2158e70e) | 108 | $7k | +2.1% (4.5) | +1.2% | -10.5% (-0.4) | +1.5% (1.9) | -0.4% | 17% | +$1k (4) | moneyline 69% | 2026-10-25 | sharp |
| 15 | [0x65b9e20f](https://polymarket.com/profile/0x65b9e20ffdb8289dc1190b9db7ec89fbbd18ff15) | 44 | $409k | +1.5% (4.4) | +0.6% | -3.3% (-0.4) | -0.1% (-0.4) | -1.3% | 81% | -$19k (49) | moneyline 100% | 2026-05-04 | sharp |
| 16 | [0xbc088291](https://polymarket.com/profile/0xbc088291a19f61cf97bd9a191740aa621cfc6b85) | 948 | $61k | +1.5% (4.4) | +1.5% | -11.6% (-2.9) | +0.7% (1.8) | -1.0% | 1% | -$0k (3) | moneyline 96% | 2026-09-16 | sharp |
| 17 | [0x3dcf59b8](https://polymarket.com/profile/0x3dcf59b8c61b12f900e96e034025a1137a384eb4) | 336 | $53k | +1.6% (4.4) | +1.6% | +3.1% (0.6) | +1.4% (3.8) | +1.4% | 2% | +$1k (45) | moneyline 99% | 2026-03-30 | copyable |
| 18 | [0xe062f353](https://polymarket.com/profile/0xe062f353e147690ff6ac405d03b2a69391fe4907) | 300 | $30k | +2.4% (4.4) | +2.4% | +0.6% (0.1) | +2.4% (3.3) | +0.8% | 1% | +$0k (3) | moneyline 82% | 2026-05-21 | copyable |
| 19 | [0x200ffb57](https://polymarket.com/profile/0x200ffb575b936d297fcf39076ddf2b476ae07a96) | 6310 | $797k | +1.3% (4.2) | +1.0% | +3.9% (2.9) | -0.1% (-0.9) | -1.9% | 93% | -$2k (179) | moneyline 65% | 2026-10-28 | sharp |
| 20 | [0x0b567742](https://polymarket.com/profile/0x0b567742aab0652a9ba7e537958e2346aa09a082) | 438 | $9k | +2.1% (4.2) | +2.0% | -4.3% (-1.0) | +1.8% (3.9) | +0.1% | 2% | -$0k (26) | moneyline 100% | 2026-09-11 | copyable |
| 21 | [0xf26817d9](https://polymarket.com/profile/0xf26817d96bf629d381e16027492b53c01793ab74) | 54 | $5k | +8.8% (4.2) | +8.8% | -13.2% (-1.0) | +7.2% (4.6) | +6.0% | 0% | -$0k (1) | moneyline 80% | 2026-06-19 | copyable |
| 22 | [0x6f2e5224](https://polymarket.com/profile/0x6f2e5224a1cc61ab6745a334ccc7d4a7bd6b7c7b) | 844 | $68k | +1.7% (4.1) | +1.7% | +3.3% (0.8) | +1.4% (3.2) | +0.2% | 7% | -$1k (539) | moneyline 99% | 2026-09-01 | copyable |
| 23 | [0x0d10fdbc](https://polymarket.com/profile/0x0d10fdbccf762e55a70e7df0856fb6914cb1780b) | 1717 | $15k | +2.5% (4.0) | +2.5% | +2.3% (1.1) | +2.0% (2.5) | +0.3% | 0% | -$1k (3538) | moneyline 50% | 2026-10-28 | copyable |
| 24 | [0x6d3c5bd1](https://polymarket.com/profile/0x6d3c5bd13984b2de47c3a88ddc455309aab3d294) | 3288 | $10.4M | +1.0% (4.0) | +0.2% | -0.2% (-0.2) | -0.2% (-2.4) | -2.3% | 91% | +$34k (400) | moneyline 84% | 2026-10-28 | sharp |
| 25 | [0xa5901037](https://polymarket.com/profile/0xa5901037a051f56a3ed55f6aee11d31e8bbf271c) | 631 | $5k | +1.7% (3.9) | +1.7% | -5.7% (-1.5) | +0.7% (2.4) | -0.7% | 0% | -$0k (418) | moneyline 58% | 2026-05-12 | copyable |
| 26 | [0xf8831548](https://polymarket.com/profile/0xf8831548531d56ad6a4331493243c447a827cd1f) | 22 | $18.1M | +1.3% (3.9) | +1.3% | +21.0% (2.3) | +1.8% (4.4) | +1.1% | 5% | +$398k (12) | moneyline 100% | 2026-06-07 | copyable |
| 27 | [0xfded52bd](https://polymarket.com/profile/0xfded52bda7eecbb4ca95e301bf6c972baef7312c) | 24 | $22k | +2.6% (3.9) | +2.8% | -6.9% (-0.3) | +2.9% (3.6) | +2.1% | 35% | +$1k (2) | moneyline 100% | 2026-06-12 | copyable |
| 28 | [0x18895028](https://polymarket.com/profile/0x188950283e983e3d0d70a115e1fac6d033900714) | 188 | $24k | +2.9% (3.8) | +3.1% | +5.0% (0.8) | +1.8% (3.4) | +1.8% | 41% | -$0k (26) | moneyline 100% | 2026-02-01 | copyable |
| 29 | [0x73afc816](https://polymarket.com/profile/0x73afc8160c17830c0c7281a7bf570c871455b880) | 58 | $1.2M | +17.6% (3.8) | +6.8% | +6.4% (6.2) | +0.6% (2.3) | -1.2% | 66% | +$87k (39) | moneyline 75% | 2026-07-22 | copyable |
| 30 | [0x2b9d225b](https://polymarket.com/profile/0x2b9d225b094a9dc54658b776314da2313ec03373) | 84 | $7k | +3.7% (3.7) | +3.7% | +0.3% (0.0) | -0.6% (-0.5) | -3.0% | 0% | +$1k (218) | moneyline 59% | 2026-10-28 | sharp |

## Winning record: ROI above zero and over 60% of bets won

A bet is the wallet's net pre-match position in one market. Win rate ignores the price paid (backing 80c favourites wins 80% and can still lose money), so read it with ROI and CLV. Sorted by ROI t-statistic.

| # | Wallet | Matches | Bets | Win rate | Pre-match stake | ROI (t) | Taker CLV (t) | Copy CLV (t) | Copy after fees | Main bet type | Last match | Also CLV-sharp |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | [0xb5b5632a](https://polymarket.com/profile/0xb5b5632a104ffaaf2145ecf2b33c3fcf8f59484e) | 41 | 41 | 63% | $9k | +139.3% (9.1) | -0.4% (-0.5) | +1.2% (2.3) | -0.7% | moneyline 100% | 2026-10-21 |  |
| 2 | [0xd0c7f0d4](https://polymarket.com/profile/0xd0c7f0d430bf1ec764a8279a75235fb5e54e4459) | 37 | 37 | 78% | $7k | +12.0% (6.5) | -0.0% (-0.1) | -0.0% (-0.1) | -0.7% | moneyline 100% | 2026-10-28 |  |
| 3 | [0xf5fe759c](https://polymarket.com/profile/0xf5fe759cece500f58a431ef8dacea321f6e3e23d) | 206 | 367 | 90% | $1.7M | +9.4% (6.4) | +23.3% (5.2) | +1.7% (3.2) | +0.2% | moneyline 88% | 2026-10-26 | yes |
| 4 | [0x57b9589d](https://polymarket.com/profile/0x57b9589d540c74aa5c9663b2f3d687d4a7ec4385) | 28 | 30 | 63% | $9k | +2.0% (6.2) | -0.2% (-2.9) | -0.2% (-6.2) | -0.2% | moneyline 100% | 2026-05-05 |  |
| 5 | [0x73afc816](https://polymarket.com/profile/0x73afc8160c17830c0c7281a7bf570c871455b880) | 58 | 358 | 99% | $1.2M | +6.4% (6.2) | +17.6% (3.8) | +0.6% (2.3) | -1.2% | moneyline 75% | 2026-07-22 | yes |
| 6 | [0xc3e550fa](https://polymarket.com/profile/0xc3e550fae1c90b71675f3355e5864c240bea519d) | 28 | 28 | 96% | $42k | +5.7% (6.1) | -1.6% (-2.2) | -0.8% (-1.4) | -1.2% | moneyline 100% | 2026-10-08 |  |
| 7 | [0x88f17731](https://polymarket.com/profile/0x88f17731836942b533f33958a302fb4c31bad3d0) | 20 | 20 | 100% | $9k | +5.7% (5.8) | -0.6% (-1.2) | -0.6% (-0.8) | -0.7% | moneyline 100% | 2026-05-24 |  |
| 8 | [0x72e15978](https://polymarket.com/profile/0x72e1597864456eda62878413cf3e60c332e4a45d) | 69 | 194 | 88% | $190k | +1.3% (5.4) | +1.8% (0.8) | +0.8% (1.1) | -1.3% | moneyline 68% | 2026-10-26 |  |
| 9 | [0x09ad5862](https://polymarket.com/profile/0x09ad5862d92d829116ecc6d55c2bf28ab20e819e) | 23 | 27 | 81% | $44k | +27.8% (4.9) | -1.1% (-3.8) | -0.4% (-1.1) | -0.4% | moneyline 85% | 2026-06-20 |  |
| 10 | [0x007f5b6c](https://polymarket.com/profile/0x007f5b6c79234ba951349fc5e67134b7afe5640f) | 34 | 34 | 94% | $8k | +9.6% (4.8) | -0.4% (-1.3) | -0.1% (-0.4) | -0.3% | moneyline 100% | 2026-06-03 |  |
| 11 | [0x67706ec3](https://polymarket.com/profile/0x67706ec33d1bc5ed0db5cf0681b74b57b64ec3bd) | 84 | 84 | 62% | $14k | +43.1% (4.6) | +3.9% (1.6) | +4.2% (1.5) | +2.7% | moneyline 98% | 2026-10-06 |  |
| 12 | [0x3fe9b9d0](https://polymarket.com/profile/0x3fe9b9d03ef21865b458479e3aa77079b00850e5) | 116 | 116 | 94% | $41k | +8.4% (4.3) | +22.9% (1.2) | -3.4% (-1.5) | -3.7% | completed match 100% | 2026-10-09 |  |
| 13 | [0xd8b4d1e5](https://polymarket.com/profile/0xd8b4d1e58dc7d60ddc886bcb9d456eb5da887773) | 42 | 327 | 95% | $822k | +8.4% (4.1) | +24.0% (3.4) | -0.0% (-0.0) | -2.5% | moneyline 81% | 2026-10-20 | yes |
| 14 | [0xe571312e](https://polymarket.com/profile/0xe571312e35abba675df3238d5e3887863cbf8492) | 112 | 112 | 96% | $40k | +6.7% (4.1) | -4.0% (-0.8) | +1.4% (0.6) | +1.0% | completed match 100% | 2026-10-09 |  |
| 15 | [0xe0f383ea](https://polymarket.com/profile/0xe0f383ea07fb3480ec5e07180c00f32284c94a02) | 114 | 114 | 94% | $38k | +7.1% (4.0) | +7.1% (1.2) | -6.5% (-2.4) | -6.8% | completed match 100% | 2026-10-09 |  |
| 16 | [0x211dcd07](https://polymarket.com/profile/0x211dcd077d0971504e9b421185e3bd5df8d73ab7) | 74 | 74 | 66% | $23k | +32.4% (3.5) | -0.6% (-1.6) | +0.6% (1.2) | -0.2% | moneyline 76% | 2026-06-10 |  |
| 17 | [0x37cc45f5](https://polymarket.com/profile/0x37cc45f56087260211f3142a57134a6ab7728792) | 137 | 137 | 94% | $45k | +8.2% (3.5) | +18.5% (0.9) | -5.4% (-3.3) | -5.7% | completed match 100% | 2026-10-09 |  |
| 18 | [0xf32de582](https://polymarket.com/profile/0xf32de5829daae9ab35a9ece9200bc0a43f64bbbb) | 59 | 59 | 64% | $42k | +28.3% (3.4) | +0.1% (0.1) | +1.0% (1.4) | +0.6% | moneyline 98% | 2026-10-27 |  |
| 19 | [0xfc4191ae](https://polymarket.com/profile/0xfc4191aede8e9685c5f1b1032ac7ec236922479d) | 284 | 284 | 96% | $30k | +5.3% (3.4) | n/a (n/a) | -2.3% (-1.8) | -2.6% | completed match 100% | 2026-10-09 |  |
| 20 | [0x986b121c](https://polymarket.com/profile/0x986b121c40e715167dde178b8520bf132a57bdc6) | 24 | 24 | 67% | $20k | +14.7% (3.4) | -0.4% (-15.2) | +1.4% (1.7) | +0.9% | moneyline 100% | 2026-10-13 |  |
| 21 | [0x8406252b](https://polymarket.com/profile/0x8406252bf81491009c1bca9b78b322cd21ec0176) | 22 | 22 | 73% | $28k | +16.7% (3.4) | +0.0% (0.1) | -0.2% (-0.4) | -0.2% | moneyline 98% | 2026-04-16 |  |
| 22 | [0x17cb6a89](https://polymarket.com/profile/0x17cb6a89c4276a7403e18126957d121a34353ab8) | 34 | 34 | 88% | $117k | +7.5% (3.3) | -0.9% (-1.6) | -0.3% (-0.5) | -0.5% | moneyline 100% | 2026-10-12 |  |
| 23 | [0xa1f699a9](https://polymarket.com/profile/0xa1f699a9c96b793bf145b9dedce8c7b6f5370981) | 40 | 41 | 66% | $10k | +12.4% (3.3) | +0.7% (1.7) | +1.2% (3.5) | +0.3% | moneyline 100% | 2026-06-07 |  |
| 24 | [0xa1089452](https://polymarket.com/profile/0xa1089452f0224a9973505f2d4347c2ea2f08abd3) | 30 | 30 | 77% | $23k | +13.1% (3.2) | +0.2% (0.4) | +0.6% (1.8) | -0.3% | moneyline 100% | 2026-10-28 |  |
| 25 | [0x29de877f](https://polymarket.com/profile/0x29de877f028c7cc7c3adb464fa108bd2ce6902aa) | 33 | 33 | 64% | $12k | +51.8% (3.2) | -1.8% (-3.1) | -0.6% (-0.9) | -0.6% | moneyline 100% | 2026-02-15 |  |
| 26 | [0xc7f66468](https://polymarket.com/profile/0xc7f66468c5d13a49595c08f18a2d7e6672f5c73d) | 253 | 253 | 96% | $26k | +5.8% (3.2) | n/a (n/a) | -0.8% (-0.7) | -1.1% | completed match 100% | 2026-10-09 |  |
| 27 | [0x09ec25a4](https://polymarket.com/profile/0x09ec25a4db8c3c731cd52337fe433408ca31f5b5) | 23 | 23 | 78% | $11k | +22.0% (3.2) | -1.5% (-1.2) | -0.9% (-0.7) | -0.9% | moneyline 100% | 2026-01-10 |  |
| 28 | [0x38723c33](https://polymarket.com/profile/0x38723c33d281011480aa2dc361be5b75c7b81fb4) | 125 | 125 | 92% | $46k | +6.3% (3.1) | +13.6% (1.2) | -0.8% (-0.3) | -1.1% | completed match 99% | 2026-10-09 |  |
| 29 | [0x7d267b9f](https://polymarket.com/profile/0x7d267b9f8fd7a80026f3676c0108620c0351ccb8) | 80 | 80 | 74% | $14k | +11.0% (3.1) | -0.4% (-1.8) | +0.0% (0.0) | -0.1% | moneyline 100% | 2026-09-11 |  |
| 30 | [0x1e89b58b](https://polymarket.com/profile/0x1e89b58b439c1c6f46308779a2356c33a4f3af95) | 22 | 23 | 83% | $13k | +51.3% (3.1) | -0.4% (-1.2) | +0.3% (1.1) | -1.8% | moneyline 75% | 2026-10-13 |  |

## Top 30 in-play by markout t-statistic

**Markout** is how far the price moved in the bettor's favour 5 minutes after their in-play taker bets, per dollar. **Copy markout** is the same for a follower buying 120 s later. Live prices jump on every point, so only a big t means anything.

| # | Wallet | In-play matches | In-play stake | Markout (t) | Copy markout (t) | Copy after fees | Live P&L | Maker | Last match | Flag |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | [0xde9f7f4e](https://polymarket.com/profile/0xde9f7f4e77a1595623ceb58e469f776257ccd43c) | 7945 | $29.7M | +4.7% (24.4) | -0.4% (-2.0) | -1.6% | +$569k | 14% | 2026-10-28 | sharp |
| 2 | [0x42c99f38](https://polymarket.com/profile/0x42c99f38d2b951b0dc8e8bd5371fa80c9dd19623) | 6568 | $18.8M | +5.3% (19.4) | -0.1% (-0.4) | -1.4% | +$505k | 27% | 2026-10-28 | sharp |
| 3 | [0xa509ae94](https://polymarket.com/profile/0xa509ae942ac8d8bc3f8c5df30cb6ae2c9b13ae46) | 7868 | $3.7M | +2.1% (18.8) | +0.2% (2.0) | -0.7% | +$43k | 62% | 2026-10-28 | copyable |
| 4 | [0x60a32ad6](https://polymarket.com/profile/0x60a32ad6f44ae555507b464268f499252c613850) | 965 | $295k | +4.4% (17.5) | +0.4% (1.7) | -0.7% | +$10k | 0% | 2026-06-04 | sharp |
| 5 | [0x205b4e3a](https://polymarket.com/profile/0x205b4e3ab6e69e2250ccfdcf4e4613287966d66a) | 275 | $47k | +7.6% (17.0) | +10.4% (1.7) | +10.1% | +$4k | 0% | 2026-08-19 | sharp |
| 6 | [0xeea3f08e](https://polymarket.com/profile/0xeea3f08e8a36081233e4c4b4142fd61a7b56a6a2) | 5532 | $14.6M | +2.8% (16.7) | -0.1% (-0.8) | -1.6% | +$155k | 0% | 2026-10-28 | sharp |
| 7 | [0x98db8cca](https://polymarket.com/profile/0x98db8cca55c32b24cfb414b5b43d273f4e1fdd17) | 7304 | $16.3M | +2.0% (14.6) | +0.1% (0.8) | -1.1% | +$203k | 56% | 2026-10-28 | sharp |
| 8 | [0x6485f47d](https://polymarket.com/profile/0x6485f47d0344c03eb4340f985159f6eb2dcba265) | 4117 | $8.2M | +5.3% (14.0) | +0.0% (0.1) | -1.5% | +$221k | 20% | 2026-10-28 | sharp |
| 9 | [0x204f72f3](https://polymarket.com/profile/0x204f72f35326db932158cba6adff0b9a1da95e14) | 6229 | $57.9M | +2.2% (13.5) | -0.2% (-1.1) | -1.0% | +$556k | 17% | 2026-08-26 | sharp |
| 10 | [0x0f17aacb](https://polymarket.com/profile/0x0f17aacbaa5e2382b44fddc45a3ed42f84d70724) | 2803 | $3.0M | +4.7% (13.2) | +0.2% (0.5) | -1.6% | +$55k | 19% | 2026-10-28 | sharp |
| 11 | [0x85630920](https://polymarket.com/profile/0x85630920a4199fb360724c2e07492b343cdf5e98) | 209 | $18k | +7.2% (12.0) | +1.6% (0.7) | +1.2% | +$1k | 0% | 2026-10-28 | sharp |
| 12 | [0x4abdea21](https://polymarket.com/profile/0x4abdea21c609efca17160f1dcbc652ba498a5a5c) | 1003 | $339k | +4.9% (10.4) | +0.2% (0.5) | -1.7% | +$10k | 0% | 2026-10-23 | sharp |
| 13 | [0xf0ea0711](https://polymarket.com/profile/0xf0ea0711aa08556fc9a4d0f8ca379254de2f2f71) | 1058 | $346k | +4.5% (9.5) | +0.4% (0.8) | -1.4% | +$8k | 0% | 2026-10-23 | sharp |
| 14 | [0x85583637](https://polymarket.com/profile/0x8558363730682d7aab94e544b21741a20df88615) | 967 | $327k | +5.1% (9.4) | +0.4% (1.0) | -1.4% | +$11k | 0% | 2026-10-28 | sharp |
| 15 | [0xe839e7fe](https://polymarket.com/profile/0xe839e7fe9cbd0997200c83d0fb77e7c290a10a9d) | 1120 | $344k | +5.6% (9.0) | -0.4% (-1.1) | -2.3% | +$14k | 0% | 2026-10-25 | sharp |
| 16 | [0x0f76e9a9](https://polymarket.com/profile/0x0f76e9a901b9b18b0ac0561556079aa4f0a6dcc9) | 3838 | $1.9M | +2.0% (8.8) | +0.2% (1.1) | -1.4% | +$4k | 29% | 2026-10-28 | sharp |
| 17 | [0xb595d09c](https://polymarket.com/profile/0xb595d09ce5bbc4d39e3b3d04e80c402d2c8d5922) | 367 | $536k | +8.1% (8.2) | +5.6% (2.3) | +5.1% | +$43k | 1% | 2026-10-20 | copyable |
| 18 | [0xd32e92fd](https://polymarket.com/profile/0xd32e92fdcaf41c886400bdc747525ca22f03b577) | 1056 | $345k | +4.6% (8.0) | -0.5% (-1.3) | -2.3% | +$11k | 0% | 2026-10-23 | sharp |
| 19 | [0xd2e82092](https://polymarket.com/profile/0xd2e820929e3940f5e1a8810f3ebfafb25c3dc60e) | 1007 | $335k | +4.9% (7.9) | -0.2% (-0.4) | -2.0% | +$11k | 0% | 2026-10-23 | sharp |
| 20 | [0xae5123e8](https://polymarket.com/profile/0xae5123e8a2f7125e9479d5916b37b7274ab61d03) | 483 | $2.6M | +4.3% (7.8) | -0.4% (-0.7) | -1.8% | +$59k | 15% | 2026-10-28 | sharp |
| 21 | [0x821dab05](https://polymarket.com/profile/0x821dab0565ebf5b327f51db06223fdcfe01acf16) | 2778 | $15.7M | +2.5% (7.7) | +0.7% (2.4) | -0.7% | +$322k | 19% | 2026-10-28 | copyable |
| 22 | [0x88f9a9b2](https://polymarket.com/profile/0x88f9a9b2878aa55d7763543fc7255d216c555c03) | 1027 | $323k | +5.0% (7.4) | +0.6% (1.4) | -1.1% | +$8k | 0% | 2026-10-23 | sharp |
| 23 | [0xbb3eaeb8](https://polymarket.com/profile/0xbb3eaeb82973aa8f140ae596f792fcdbd9cab9c5) | 1044 | $341k | +4.7% (7.4) | +0.1% (0.2) | -1.7% | +$9k | 0% | 2026-10-25 | sharp |
| 24 | [0x0d2d845a](https://polymarket.com/profile/0x0d2d845a6ff64e31e04a70afce8a573940767ff5) | 4014 | $34.3M | +4.8% (7.4) | +0.3% (0.4) | -1.4% | +$13k | 99% | 2026-10-28 | sharp |
| 25 | [0x31121402](https://polymarket.com/profile/0x31121402eafd4a157141db8f84b5da297ff63fcd) | 191 | $14k | +8.4% (7.1) | +3.0% (0.6) | +2.4% | +$1k | 0% | 2026-10-28 | sharp |
| 26 | [0xa7761028](https://polymarket.com/profile/0xa776102843c70456cb25060090507790888ea17b) | 20 | $14k | +4.6% (6.8) | +4.1% (16.4) | +4.1% | +$1k | 89% | 2026-02-04 | copyable |
| 27 | [0xda179b2e](https://polymarket.com/profile/0xda179b2ebef1c02f50a28efd5dd57b3834ea9b48) | 21 | $12k | +8.2% (6.7) | +1.6% (2.0) | -0.3% | +$0k | 15% | 2026-10-16 | sharp |
| 28 | [0xab417c0b](https://polymarket.com/profile/0xab417c0bacc9fe17368d5d662c957f54a1fcc453) | 289 | $47k | +11.1% (6.5) | +4.1% (2.0) | +2.0% | -$0k | 74% | 2026-08-29 | copyable |
| 29 | [0x972bf37c](https://polymarket.com/profile/0x972bf37cae72a169e17ae0e6179821d5778b78ba) | 1812 | $9.2M | +1.3% (6.4) | +0.2% (1.0) | -0.2% | +$60k | 65% | 2026-04-10 | sharp |
| 30 | [0x7ca56b03](https://polymarket.com/profile/0x7ca56b03105371839e4a3d98f4c1059d10d784bc) | 48 | $6k | +7.2% (6.4) | +12.8% (1.6) | +11.1% | +$0k | 1% | 2026-06-26 | sharp |

## Caveats

* The close and the copy price come from the trade tape, not order books (Polymarket keeps no historical books), so they mix bid and ask prints. Thin alternate lines have noisy closes.
* Pre-match fills priced below 3c or above 97c, and fills after a market closed, are left out: they carry no information about skill.
* In-play bets have no closing line, so they do not affect the pre-match rank; they are scored on the price 5 minutes later instead.
* A wallet can be one person with several wallets, or a bot. Maker share near 100% usually means a market maker earning the spread, which is not copyable even when CLV is positive.
* Match start times are Polymarket's listed times. When the moneyline swings like live play in the hour before the listed start, the match is treated as started at that swing.
