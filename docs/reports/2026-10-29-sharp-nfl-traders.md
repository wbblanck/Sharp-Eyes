# Sharp NFL traders on Polymarket

Games 2025-09-05 to 2026-10-27: 441 settled NFL games, 5,027,182 fills, 127,473 wallets. Ranked: 1,169 wallets with aggressive (taker) bets before kickoff in at least 20 games and $5k staked pre-game.

* **Flagged sharp** (their taker bets beat the closing line, false-discovery rate under 5%): 9
* **Still worth copying** after a 120 s delay (sharp, and the delayed price still beats the close with t >= 2): 5

Columns: **Taker CLV** is the average edge of the wallet's aggressive pre-game bets versus the closing price, per dollar staked (+2% means they bought 2% cheaper than the close); the rank uses its t-statistic. **All CLV** adds their resting limit orders, which pick up half the spread for free. **ROI** is the settled pre-game result after taker fees. **Copy CLV** is the CLV a follower would get buying 120 s later, on all of the wallet's pre-game fills. t is the t-statistic, clustered by game; about 3 or more is unlikely to be luck. **Maker** is the share of stake filled as resting limit orders. **Live P&L** is the in-game result in dollars.

## Does it persist? Ranked on games before 2026-08-01, measured after

Ranking used 285 games; the check uses the 156 games after. Rank correlation between earlier CLV t and later taker CLV, over 167 wallets active in both: **0.39**.

| Group | Wallets active after | Stake after | Taker CLV after | All CLV after | ROI after | Copy CLV after |
|---|---:|---:|---:|---:|---:|---:|
| Flagged sharp before split (q < 0.05, 5 wallets) | 1 | $1k | -0.5% | -0.5% | +51.9% | +9.0% |
| Top 25 before split | 5 | $850k | +1.1% | +0.3% | -23.5% | -0.1% |
| Bottom 25 before split | 9 | $171k | -1.2% | -1.2% | +3.4% | -0.1% |
| Every wallet | 16886 | $293.8M | -0.1% | +0.0% | -0.3% | +0.0% |

## Top 30 by taker CLV t-statistic

| # | Wallet | Games | Pre-game stake | Taker CLV (t) | All CLV | ROI (t) | Copy CLV (t) | Maker | Live P&L (games) | Main bet type | Last game | Flag |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | [0x033f0346](https://polymarket.com/profile/0x033f0346c007323030eb420305ffede19a95618e) | 47 | $7k | +41.8% (4.9) | +41.8% | -27.2% (-0.7) | +17.4% (2.2) | 6% | +$21k (95) | spread 70% | 2026-10-25 | copyable |
| 2 | [0x09b54073](https://polymarket.com/profile/0x09b540739cfa17ba6b61f4351000583cd6397e72) | 28 | $30k | +1.6% (4.9) | +1.6% | -6.8% (-0.2) | +1.9% (11.1) | 0% | -$0k (32) | spread 77% | 2026-10-27 | copyable |
| 3 | [0xbc43c8bf](https://polymarket.com/profile/0xbc43c8bfbc4d77c2fc9011adad38ba43b88996d3) | 75 | $6.5M | +3.0% (4.7) | +2.1% | +16.7% (1.0) | +1.9% (4.4) | 64% | -$29k (27) | spread 58% | 2026-10-27 | copyable |
| 4 | [0xee613b3f](https://polymarket.com/profile/0xee613b3fc183ee44f9da9c05f53e2da107e3debf) | 209 | $8.1M | +0.8% (4.6) | +1.0% | +2.8% (1.0) | +0.1% (1.3) | 70% | +$24k (57) | spread 39% | 2026-02-08 | sharp |
| 5 | [0x51393c00](https://polymarket.com/profile/0x51393c00184b39182f09a8a62b8549642e69a8db) | 212 | $7.0M | +0.6% (4.0) | +0.6% | +0.8% (0.1) | +0.9% (5.6) | 3% | -$23k (108) | moneyline 79% | 2025-12-16 | copyable |
| 6 | [0x924379a7](https://polymarket.com/profile/0x924379a79c64b77ad5816ad362122a5f6228658e) | 51 | $7.0M | +1.2% (3.9) | +1.2% | +9.8% (0.6) | +0.1% (0.3) | 4% | +$0k (0) | spread 42% | 2026-10-25 | sharp |
| 7 | [0xdd5ef115](https://polymarket.com/profile/0xdd5ef115f801999575b03d78d0115ad8b2d59040) | 136 | $305k | +1.5% (3.7) | +1.3% | -10.1% (-1.1) | +1.9% (4.8) | 9% | +$1k (25) | spread 55% | 2026-10-27 | copyable |
| 8 | [0x507e52ef](https://polymarket.com/profile/0x507e52ef684ca2dd91f90a9d26d149dd3288beae) | 136 | $3.3M | +1.5% (3.6) | +1.8% | +7.5% (1.0) | +0.3% (0.6) | 70% | +$68k (134) | moneyline 42% | 2026-02-08 | sharp |
| 9 | [0x31519628](https://polymarket.com/profile/0x31519628fb5e5aa559d4ba27aa1248810b9f0977) | 42 | $1.2M | +1.7% (3.5) | +0.7% | +12.8% (0.8) | +0.1% (0.3) | 50% | +$92k (77) | moneyline 39% | 2025-11-16 | sharp |
| 10 | [0xb13d096b](https://polymarket.com/profile/0xb13d096b2e90411d0e5f42891d2e73ef4cea2e90) | 282 | $4.4M | +0.7% (3.2) | +0.9% | +1.6% (1.2) | +0.5% (3.4) | 54% | +$17k (78) | moneyline 100% | 2026-02-08 |  |
| 11 | [0x3cdaf931](https://polymarket.com/profile/0x3cdaf931c538750ffa43b4de25366401d7446e17) | 80 | $10.3M | +1.4% (3.0) | +0.7% | -8.1% (-1.5) | +0.2% (1.6) | 91% | +$183k (32) | moneyline 87% | 2025-11-14 |  |
| 12 | [0x1455445e](https://polymarket.com/profile/0x1455445e9a775cfa3fe9fc4b02bb4d2f682ae5cd) | 88 | $3.1M | +0.7% (3.0) | +0.7% | -10.5% (-1.0) | +1.1% (5.0) | 2% | -$128k (19) | moneyline 74% | 2026-02-08 |  |
| 13 | [0x1f3a646c](https://polymarket.com/profile/0x1f3a646ce5cbe2c70270e7a46161d89b7c7b895d) | 57 | $7.4M | +1.6% (2.9) | +0.3% | +9.3% (0.7) | +0.0% (0.1) | 74% | -$381k (54) | spread 43% | 2026-10-27 |  |
| 14 | [0x6d3c5bd1](https://polymarket.com/profile/0x6d3c5bd13984b2de47c3a88ddc455309aab3d294) | 271 | $11.1M | +0.5% (2.9) | -0.0% | +1.1% (0.9) | -0.1% (-1.6) | 82% | -$70k (48) | spread 48% | 2026-10-27 |  |
| 15 | [0x684baa57](https://polymarket.com/profile/0x684baa57c338c2549aec0aa3f034f695d72a8409) | 82 | $2.3M | +2.0% (2.9) | +0.2% | -11.8% (-1.1) | +0.0% (0.1) | 85% | +$8k (4) | spread 44% | 2026-10-27 |  |
| 16 | [0xe8a8cc88](https://polymarket.com/profile/0xe8a8cc8877e2af6712174d2d2e8745f4f32ea48e) | 59 | $1.0M | +1.0% (2.9) | +1.0% | +9.3% (0.5) | +1.3% (3.1) | 8% | -$1k (7) | moneyline 97% | 2026-02-08 |  |
| 17 | [0xb786b8b6](https://polymarket.com/profile/0xb786b8b6335e77dfad19928313e97753039cb18d) | 160 | $1.0M | +1.6% (2.8) | +1.0% | +3.9% (0.7) | -0.2% (-0.7) | 70% | -$3k (111) | moneyline 100% | 2026-02-08 |  |
| 18 | [0x67542c32](https://polymarket.com/profile/0x67542c3219b37fd1610aad290676ff91cdbfe3bc) | 77 | $14.0M | +0.4% (2.7) | +0.1% | +0.3% (0.0) | +0.1% (0.5) | 39% | +$641k (29) | moneyline 51% | 2026-10-27 |  |
| 19 | [0x16b29c50](https://polymarket.com/profile/0x16b29c50f2439faf627209b2ac0c7bbddaa8a881) | 170 | $26.6M | +1.0% (2.6) | +0.7% | +7.5% (0.7) | +0.3% (0.5) | 43% | +$164k (92) | spread 56% | 2026-01-13 |  |
| 20 | [0x54ce7dd3](https://polymarket.com/profile/0x54ce7dd357766fc3255645e55ef41edd51cc9f80) | 31 | $183k | +6.8% (2.6) | +3.5% | +8.9% (0.4) | +3.1% (1.3) | 26% | +$17k (3) | moneyline 52% | 2026-10-25 |  |
| 21 | [0xa2cced8b](https://polymarket.com/profile/0xa2cced8bfae7d645f7f437fb76becf2fcbb70cbc) | 52 | $2.1M | +1.2% (2.5) | +1.5% | +2.1% (0.1) | +1.3% (2.6) | 69% | +$1k (2) | spread 50% | 2026-10-25 |  |
| 22 | [0xe90bec87](https://polymarket.com/profile/0xe90bec87d9ef430f27f9dcfe72c34b76967d5da2) | 66 | $8.0M | +0.7% (2.5) | +1.1% | +9.3% (0.5) | -0.1% (-0.3) | 61% | -$419k (82) | moneyline 65% | 2026-02-08 |  |
| 23 | [0xe83cc0c8](https://polymarket.com/profile/0xe83cc0c82d009a1c349c1a89feaadfcee9655e8f) | 148 | $154k | +1.1% (2.4) | +1.6% | +21.8% (2.4) | -0.1% (-0.2) | 76% | +$3k (21) | spread 42% | 2025-12-30 |  |
| 24 | [0x57a8d637](https://polymarket.com/profile/0x57a8d63731277200ed26cfde9a8a830d94f36933) | 129 | $1.3M | +1.8% (2.4) | +1.5% | -4.8% (-0.4) | +1.0% (1.5) | 24% | +$39k (10) | moneyline 48% | 2026-02-08 |  |
| 25 | [0xe542afd3](https://polymarket.com/profile/0xe542afd3881c4c330ba0ebbb603bb470b2ba0a37) | 26 | $85k | +7.4% (2.3) | +3.8% | +3.7% (2.6) | +3.0% (2.0) | 43% | +$0k (48) | moneyline 99% | 2026-10-18 |  |
| 26 | [0xa3d38f81](https://polymarket.com/profile/0xa3d38f810aa438533f1abfd7510e1b130126f2bc) | 47 | $31k | +0.7% (2.3) | +0.4% | +19.2% (2.4) | +0.1% (0.1) | 59% | +$1k (6) | moneyline 70% | 2026-02-08 |  |
| 27 | [0xec136933](https://polymarket.com/profile/0xec1369338d55b6e2baba1fed61f533d86431862b) | 34 | $76k | +1.7% (2.3) | +0.8% | -5.1% (-0.3) | +1.1% (1.8) | 31% | +$0k (3) | total 46% | 2026-02-08 |  |
| 28 | [0xd81e5bc0](https://polymarket.com/profile/0xd81e5bc01e4a98d0af93d82dc2c542a4c0f9e3d0) | 39 | $88k | +2.5% (2.1) | +2.0% | +12.5% (0.3) | +1.3% (2.3) | 56% | +$0k (0) | spread 84% | 2026-10-25 |  |
| 29 | [0xb406f1f3](https://polymarket.com/profile/0xb406f1f3abe02300d4504b6940f6954c238c4964) | 31 | $13k | +6.2% (2.1) | +5.3% | +22.3% (1.1) | +7.4% (2.3) | 26% | +$0k (0) | moneyline 83% | 2025-11-14 |  |
| 30 | [0x18670d5a](https://polymarket.com/profile/0x18670d5a83b7b38d509398067c095d4c321992ca) | 67 | $198k | +0.9% (2.0) | +0.4% | +21.4% (2.4) | +0.3% (1.3) | 72% | +$4k (6) | moneyline 63% | 2026-02-08 |  |

## Caveats

* The close and the copy price come from the trade tape, not order books (Polymarket keeps no historical books), so they mix bid and ask prints. Thin alternate lines have noisy closes.
* Fills priced below 3c or above 97c, and fills after a market closed, are left out: they carry no information about skill.
* In-game (live) bets have no closing line, so they count only through Live P&L and do not affect the rank.
* A wallet can be one person with several wallets, or a bot. Maker share near 100% usually means a market maker earning the spread, which is not copyable even when CLV is positive.
