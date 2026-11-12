# Sharp NFL traders on Polymarket

Games 2025-09-05 to 2026-10-27: 441 settled NFL games, 5,027,182 fills, 127,473 wallets. Ranked: 1,169 wallets with aggressive (taker) bets before kickoff in at least 20 games and $5k staked pre-game.

* **Flagged sharp** (their taker bets beat the closing line, false-discovery rate under 5%): 9
* **Still worth copying** after a 120 s delay (sharp, and the delayed price still beats the close with t >= 2): 5
* **Winning record** (profitable before kickoff and won more than 60% of bets, same game and stake floors): 187

Columns: **Taker CLV** is the average edge of the wallet's aggressive pre-game bets versus the closing price, per dollar staked (+2% means they bought 2% cheaper than the close); the rank uses its t-statistic. **All CLV** adds their resting limit orders, which pick up half the spread for free. **ROI** is the settled pre-game result after taker fees. **Copy CLV** is the CLV a follower would get buying 120 s later, on all of the wallet's pre-game fills. t is the t-statistic, clustered by game; about 3 or more is unlikely to be luck. **Maker** is the share of stake filled as resting limit orders. **Live P&L** is the in-game result in dollars.

## Does it persist? Ranked on games before 2026-08-01, measured after

Ranking used 285 games; the check uses the 156 games after. Rank correlation between earlier CLV t and later taker CLV, over 167 wallets active in both: **0.39**.

| Group | Wallets active after | Stake after | Taker CLV after | All CLV after | ROI after | Win rate after | Copy CLV after |
|---|---:|---:|---:|---:|---:|---:|---:|
| Flagged sharp before split (q < 0.05, 5 wallets) | 1 | $1k | -0.5% | -0.5% | +51.9% | 67% | +9.0% |
| Top 25 before split | 5 | $850k | +1.1% | +0.3% | -23.5% | 47% | -0.1% |
| Bottom 25 before split | 9 | $171k | -1.2% | -1.2% | +3.4% | 50% | -0.1% |
| Winning record before split (ROI > 0, wins > 60%, 165 wallets) | 59 | $15.5M | +0.1% | -0.1% | +2.6% | 54% | -0.1% |
| Every wallet | 16886 | $293.8M | -0.1% | +0.0% | -0.3% | 49% | +0.0% |

## Top 30 by taker CLV t-statistic

| # | Wallet | Games | Pre-game stake | Taker CLV (t) | All CLV | ROI (t) | Copy CLV (t) | Maker | Live P&L (games) | Main bet type | Last game | Flag |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 0x033f0346 | 47 | $7k | +41.8% (4.9) | +41.8% | -27.2% (-0.7) | +17.4% (2.2) | 6% | +$21k (95) | spread 70% | 2026-10-25 | copyable |
| 2 | 0x09b54073 | 28 | $30k | +1.6% (4.9) | +1.6% | -6.8% (-0.2) | +1.9% (11.1) | 0% | -$0k (32) | spread 77% | 2026-10-27 | copyable |
| 3 | 0xbc43c8bf | 75 | $6.5M | +3.0% (4.7) | +2.1% | +16.7% (1.0) | +1.9% (4.4) | 64% | -$29k (27) | spread 58% | 2026-10-27 | copyable |
| 4 | 0xee613b3f | 209 | $8.1M | +0.8% (4.6) | +1.0% | +2.8% (1.0) | +0.1% (1.3) | 70% | +$24k (57) | spread 39% | 2026-02-08 | sharp |
| 5 | 0x51393c00 | 212 | $7.0M | +0.6% (4.0) | +0.6% | +0.8% (0.1) | +0.9% (5.6) | 3% | -$23k (108) | moneyline 79% | 2025-12-16 | copyable |
| 6 | 0x924379a7 | 51 | $7.0M | +1.2% (3.9) | +1.2% | +9.8% (0.6) | +0.1% (0.3) | 4% | +$0k (0) | spread 42% | 2026-10-25 | sharp |
| 7 | 0xdd5ef115 | 136 | $305k | +1.5% (3.7) | +1.3% | -10.1% (-1.1) | +1.9% (4.8) | 9% | +$1k (25) | spread 55% | 2026-10-27 | copyable |
| 8 | 0x507e52ef | 136 | $3.3M | +1.5% (3.6) | +1.8% | +7.5% (1.0) | +0.3% (0.6) | 70% | +$68k (134) | moneyline 42% | 2026-02-08 | sharp |
| 9 | 0x31519628 | 42 | $1.2M | +1.7% (3.5) | +0.7% | +12.8% (0.8) | +0.1% (0.3) | 50% | +$92k (77) | moneyline 39% | 2025-11-16 | sharp |
| 10 | 0xb13d096b | 282 | $4.4M | +0.7% (3.2) | +0.9% | +1.6% (1.2) | +0.5% (3.4) | 54% | +$17k (78) | moneyline 100% | 2026-02-08 |  |
| 11 | 0x3cdaf931 | 80 | $10.3M | +1.4% (3.0) | +0.7% | -8.1% (-1.5) | +0.2% (1.6) | 91% | +$183k (32) | moneyline 87% | 2025-11-14 |  |
| 12 | 0x1455445e | 88 | $3.1M | +0.7% (3.0) | +0.7% | -10.5% (-1.0) | +1.1% (5.0) | 2% | -$128k (19) | moneyline 74% | 2026-02-08 |  |
| 13 | 0x1f3a646c | 57 | $7.4M | +1.6% (2.9) | +0.3% | +9.3% (0.7) | +0.0% (0.1) | 74% | -$381k (54) | spread 43% | 2026-10-27 |  |
| 14 | 0x6d3c5bd1 | 271 | $11.1M | +0.5% (2.9) | -0.0% | +1.1% (0.9) | -0.1% (-1.6) | 82% | -$70k (48) | spread 48% | 2026-10-27 |  |
| 15 | 0x684baa57 | 82 | $2.3M | +2.0% (2.9) | +0.2% | -11.8% (-1.1) | +0.0% (0.1) | 85% | +$8k (4) | spread 44% | 2026-10-27 |  |
| 16 | 0xe8a8cc88 | 59 | $1.0M | +1.0% (2.9) | +1.0% | +9.3% (0.5) | +1.3% (3.1) | 8% | -$1k (7) | moneyline 97% | 2026-02-08 |  |
| 17 | 0xb786b8b6 | 160 | $1.0M | +1.6% (2.8) | +1.0% | +3.9% (0.7) | -0.2% (-0.7) | 70% | -$3k (111) | moneyline 100% | 2026-02-08 |  |
| 18 | 0x67542c32 | 77 | $14.0M | +0.4% (2.7) | +0.1% | +0.3% (0.0) | +0.1% (0.5) | 39% | +$641k (29) | moneyline 51% | 2026-10-27 |  |
| 19 | 0x16b29c50 | 170 | $26.6M | +1.0% (2.6) | +0.7% | +7.5% (0.7) | +0.3% (0.5) | 43% | +$164k (92) | spread 56% | 2026-01-13 |  |
| 20 | 0x54ce7dd3 | 31 | $183k | +6.8% (2.6) | +3.5% | +8.9% (0.4) | +3.1% (1.3) | 26% | +$17k (3) | moneyline 52% | 2026-10-25 |  |
| 21 | 0xa2cced8b | 52 | $2.1M | +1.2% (2.5) | +1.5% | +2.1% (0.1) | +1.3% (2.6) | 69% | +$1k (2) | spread 50% | 2026-10-25 |  |
| 22 | 0xe90bec87 | 66 | $8.0M | +0.7% (2.5) | +1.1% | +9.3% (0.5) | -0.1% (-0.3) | 61% | -$419k (82) | moneyline 65% | 2026-02-08 |  |
| 23 | 0xe83cc0c8 | 148 | $154k | +1.1% (2.4) | +1.6% | +21.8% (2.4) | -0.1% (-0.2) | 76% | +$3k (21) | spread 42% | 2025-12-30 |  |
| 24 | 0x57a8d637 | 129 | $1.3M | +1.8% (2.4) | +1.5% | -4.8% (-0.4) | +1.0% (1.5) | 24% | +$39k (10) | moneyline 48% | 2026-02-08 |  |
| 25 | 0xe542afd3 | 26 | $85k | +7.4% (2.3) | +3.8% | +3.7% (2.6) | +3.0% (2.0) | 43% | +$0k (48) | moneyline 99% | 2026-10-18 |  |
| 26 | 0xa3d38f81 | 47 | $31k | +0.7% (2.3) | +0.4% | +19.2% (2.4) | +0.1% (0.1) | 59% | +$1k (6) | moneyline 70% | 2026-02-08 |  |
| 27 | 0xec136933 | 34 | $76k | +1.7% (2.3) | +0.8% | -5.1% (-0.3) | +1.1% (1.8) | 31% | +$0k (3) | total 46% | 2026-02-08 |  |
| 28 | 0xd81e5bc0 | 39 | $88k | +2.5% (2.1) | +2.0% | +12.5% (0.3) | +1.3% (2.3) | 56% | +$0k (0) | spread 84% | 2026-10-25 |  |
| 29 | 0xb406f1f3 | 31 | $13k | +6.2% (2.1) | +5.3% | +22.3% (1.1) | +7.4% (2.3) | 26% | +$0k (0) | moneyline 83% | 2025-11-14 |  |
| 30 | 0x18670d5a | 67 | $198k | +0.9% (2.0) | +0.4% | +21.4% (2.4) | +0.3% (1.3) | 72% | +$4k (6) | moneyline 63% | 2026-02-08 |  |

## Winning record: ROI above zero and over 60% of bets won

A bet is the wallet's net pre-game position in one market. Win rate ignores the price paid (backing 80c favourites wins 80% and can still lose money), so read it with ROI and CLV. Sorted by ROI t-statistic.

| # | Wallet | Games | Bets | Win rate | Pre-game stake | ROI (t) | Taker CLV (t) | Copy CLV (t) | Main bet type | Last game | Also CLV-sharp |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | 0x998154d8 | 30 | 30 | 93% | $189k | +22.8% (5.7) | -0.8% (-2.2) | -0.6% (-1.2) | moneyline 100% | 2026-09-13 |  |
| 2 | 0x765ccc22 | 48 | 48 | 71% | $55k | +0.5% (4.3) | -0.4% (-1.4) | +0.2% (1.1) | moneyline 100% | 2026-02-08 |  |
| 3 | 0x07c84658 | 29 | 33 | 76% | $167k | +68.4% (4.1) | -2.7% (-3.0) | +0.2% (0.3) | spread 60% | 2026-09-14 |  |
| 4 | 0xd2b2cd80 | 46 | 47 | 64% | $255k | +34.4% (4.0) | -1.4% (-2.2) | -0.9% (-1.0) | moneyline 96% | 2026-01-10 |  |
| 5 | 0x2bc7e939 | 62 | 69 | 70% | $97k | +19.3% (3.6) | +0.7% (1.9) | +0.3% (0.7) | moneyline 98% | 2026-01-11 |  |
| 6 | 0xc16e1477 | 21 | 41 | 71% | $28k | +57.6% (3.5) | -0.7% (-2.8) | +0.3% (0.9) | spread 51% | 2026-10-27 |  |
| 7 | 0x7702028f | 30 | 33 | 79% | $177k | +39.9% (3.5) | -3.0% (-3.4) | -2.3% (-2.7) | moneyline 79% | 2026-02-08 |  |
| 8 | 0x566e47c6 | 72 | 72 | 65% | $53k | +0.2% (3.4) | -0.4% (-1.3) | -0.0% (-0.1) | moneyline 100% | 2026-01-13 |  |
| 9 | 0x4fc19a90 | 291 | 301 | 73% | $1.5M | +0.6% (3.2) | -0.5% (-1.2) | -0.0% (-0.4) | moneyline 100% | 2026-10-11 |  |
| 10 | 0x37c64f63 | 33 | 47 | 62% | $42k | +31.5% (3.0) | -0.1% (-0.2) | -0.4% (-0.8) | moneyline 37% | 2026-10-27 |  |
| 11 | 0x4109b611 | 104 | 147 | 61% | $6k | +25.8% (2.9) | +0.4% (0.6) | +0.1% (0.2) | spread 44% | 2026-02-08 |  |
| 12 | 0x8a0c800b | 33 | 39 | 64% | $8k | +37.9% (2.9) | -0.0% (-0.0) | +0.6% (1.1) | spread 43% | 2026-10-25 |  |
| 13 | 0xddd757c8 | 71 | 71 | 65% | $28k | +0.1% (2.8) | -0.2% (-1.0) | -0.1% (-1.0) | moneyline 100% | 2026-02-08 |  |
| 14 | 0xa6d9d375 | 25 | 25 | 64% | $13k | +12.8% (2.8) | -0.7% (-2.7) | -0.4% (-1.6) | moneyline 100% | 2026-10-18 |  |
| 15 | 0xb3e4032a | 103 | 145 | 62% | $8k | +24.0% (2.7) | +0.2% (0.3) | +0.5% (0.9) | spread 42% | 2026-02-08 |  |
| 16 | 0x1ff26f9f | 27 | 34 | 74% | $3.5M | +46.7% (2.7) | -1.0% (-2.8) | -0.7% (-1.5) | moneyline 77% | 2026-01-25 |  |
| 17 | 0xe542afd3 | 26 | 27 | 67% | $85k | +3.7% (2.6) | +7.4% (2.3) | +3.0% (2.0) | moneyline 99% | 2026-10-18 |  |
| 18 | 0xc2a37f1e | 43 | 44 | 80% | $592k | +15.5% (2.6) | -1.5% (-6.9) | -0.5% (-2.0) | moneyline 98% | 2025-11-07 |  |
| 19 | 0xe18ecc34 | 27 | 51 | 73% | $929k | +38.3% (2.6) | -1.4% (-1.7) | -1.2% (-1.2) | spread 69% | 2026-10-25 |  |
| 20 | 0xc383e03d | 106 | 148 | 60% | $9k | +21.5% (2.5) | +1.0% (1.0) | +0.3% (0.6) | spread 44% | 2026-02-08 |  |
| 21 | 0x814ca2f4 | 77 | 77 | 71% | $154k | +0.1% (2.5) | -0.6% (-2.2) | -0.0% (-0.8) | moneyline 100% | 2026-02-08 |  |
| 22 | 0x089d01d4 | 42 | 51 | 67% | $9k | +19.1% (2.5) | -1.6% (-4.6) | -1.2% (-3.2) | moneyline 91% | 2026-02-08 |  |
| 23 | 0xa3d38f81 | 47 | 53 | 62% | $31k | +19.2% (2.4) | +0.7% (2.3) | +0.1% (0.1) | moneyline 70% | 2026-02-08 |  |
| 24 | 0xb5aa9120 | 27 | 29 | 72% | $37k | +33.6% (2.4) | -1.4% (-4.8) | -1.0% (-3.3) | moneyline 94% | 2026-10-13 |  |
| 25 | 0x82147e52 | 30 | 39 | 62% | $18k | +39.8% (2.4) | -1.2% (-1.6) | -0.4% (-0.3) | moneyline 46% | 2026-02-08 |  |
| 26 | 0x5bf68500 | 27 | 27 | 63% | $44k | +50.0% (2.4) | -0.9% (-1.7) | +0.1% (0.2) | moneyline 100% | 2026-01-25 |  |
| 27 | 0x18670d5a | 67 | 76 | 62% | $198k | +21.4% (2.4) | +0.9% (2.0) | +0.3% (1.3) | moneyline 63% | 2026-02-08 |  |
| 28 | 0xcf6c5492 | 72 | 87 | 63% | $1.1M | +16.0% (2.3) | -0.7% (-1.2) | -0.6% (-2.0) | moneyline 48% | 2026-10-25 |  |
| 29 | 0x6141759f | 22 | 23 | 61% | $66k | +8.3% (2.3) | -1.0% (-1.3) | +0.4% (0.7) | moneyline 100% | 2026-02-08 |  |
| 30 | 0xc9c8f269 | 37 | 82 | 65% | $60k | +31.8% (2.3) | +0.1% (0.5) | -1.3% (-1.8) | moneyline 48% | 2026-10-11 |  |

## Caveats

* The close and the copy price come from the trade tape, not order books (Polymarket keeps no historical books), so they mix bid and ask prints. Thin alternate lines have noisy closes.
* Fills priced below 3c or above 97c, and fills after a market closed, are left out: they carry no information about skill.
* In-game (live) bets have no closing line, so they count only through Live P&L and do not affect the rank.
* A wallet can be one person with several wallets, or a bot. Maker share near 100% usually means a market maker earning the spread, which is not copyable even when CLV is positive.
