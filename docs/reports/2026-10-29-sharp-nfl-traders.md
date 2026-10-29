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

## Winning record: ROI above zero and over 60% of bets won

A bet is the wallet's net pre-game position in one market. Win rate ignores the price paid (backing 80c favourites wins 80% and can still lose money), so read it with ROI and CLV. Sorted by ROI t-statistic.

| # | Wallet | Games | Bets | Win rate | Pre-game stake | ROI (t) | Taker CLV (t) | Copy CLV (t) | Main bet type | Last game | Also CLV-sharp |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | [0x998154d8](https://polymarket.com/profile/0x998154d8eb4ba7c4b34b10d76b9742d922d7dec4) | 30 | 30 | 93% | $189k | +22.8% (5.7) | -0.8% (-2.2) | -0.6% (-1.2) | moneyline 100% | 2026-09-13 |  |
| 2 | [0x765ccc22](https://polymarket.com/profile/0x765ccc22f446bf0da544e8d64832f70d5c6c0779) | 48 | 48 | 71% | $55k | +0.5% (4.3) | -0.4% (-1.4) | +0.2% (1.1) | moneyline 100% | 2026-02-08 |  |
| 3 | [0x07c84658](https://polymarket.com/profile/0x07c846584cbf796aea720bb41e674e6734fc2696) | 29 | 33 | 76% | $167k | +68.4% (4.1) | -2.7% (-3.0) | +0.2% (0.3) | spread 60% | 2026-09-14 |  |
| 4 | [0xd2b2cd80](https://polymarket.com/profile/0xd2b2cd8044cc7a19e12db9b09f4f12a1c3d0d101) | 46 | 47 | 64% | $255k | +34.4% (4.0) | -1.4% (-2.2) | -0.9% (-1.0) | moneyline 96% | 2026-01-10 |  |
| 5 | [0x2bc7e939](https://polymarket.com/profile/0x2bc7e939bf48259488c991b095977d1f3beee411) | 62 | 69 | 70% | $97k | +19.3% (3.6) | +0.7% (1.9) | +0.3% (0.7) | moneyline 98% | 2026-01-11 |  |
| 6 | [0xc16e1477](https://polymarket.com/profile/0xc16e1477bec0d3970b8bba3a6ea9faea73918f62) | 21 | 41 | 71% | $28k | +57.6% (3.5) | -0.7% (-2.8) | +0.3% (0.9) | spread 51% | 2026-10-27 |  |
| 7 | [0x7702028f](https://polymarket.com/profile/0x7702028f87deda0ceefea619209ece9630669791) | 30 | 33 | 79% | $177k | +39.9% (3.5) | -3.0% (-3.4) | -2.3% (-2.7) | moneyline 79% | 2026-02-08 |  |
| 8 | [0x566e47c6](https://polymarket.com/profile/0x566e47c6889d98bba7c30c5307baa1a07b6e1340) | 72 | 72 | 65% | $53k | +0.2% (3.4) | -0.4% (-1.3) | -0.0% (-0.1) | moneyline 100% | 2026-01-13 |  |
| 9 | [0x4fc19a90](https://polymarket.com/profile/0x4fc19a907012ef58717ee7ceb1f89057f71aec92) | 291 | 301 | 73% | $1.5M | +0.6% (3.2) | -0.5% (-1.2) | -0.0% (-0.4) | moneyline 100% | 2026-10-11 |  |
| 10 | [0x37c64f63](https://polymarket.com/profile/0x37c64f63fbd808b510b7a4bd3437c9991b0c92e9) | 33 | 47 | 62% | $42k | +31.5% (3.0) | -0.1% (-0.2) | -0.4% (-0.8) | moneyline 37% | 2026-10-27 |  |
| 11 | [0x4109b611](https://polymarket.com/profile/0x4109b611161b82518329c157f3f3c415ecaa7e24) | 104 | 147 | 61% | $6k | +25.8% (2.9) | +0.4% (0.6) | +0.1% (0.2) | spread 44% | 2026-02-08 |  |
| 12 | [0x8a0c800b](https://polymarket.com/profile/0x8a0c800ba720662de7188ffb997701194a353d4d) | 33 | 39 | 64% | $8k | +37.9% (2.9) | -0.0% (-0.0) | +0.6% (1.1) | spread 43% | 2026-10-25 |  |
| 13 | [0xddd757c8](https://polymarket.com/profile/0xddd757c8798761e39009e227548252c4dc3b1596) | 71 | 71 | 65% | $28k | +0.1% (2.8) | -0.2% (-1.0) | -0.1% (-1.0) | moneyline 100% | 2026-02-08 |  |
| 14 | [0xa6d9d375](https://polymarket.com/profile/0xa6d9d375f8eab5f4dd3fcc2b597ca68b7be168a3) | 25 | 25 | 64% | $13k | +12.8% (2.8) | -0.7% (-2.7) | -0.4% (-1.6) | moneyline 100% | 2026-10-18 |  |
| 15 | [0xb3e4032a](https://polymarket.com/profile/0xb3e4032a53865af9eac182b59502407c0e9cd6b2) | 103 | 145 | 62% | $8k | +24.0% (2.7) | +0.2% (0.3) | +0.5% (0.9) | spread 42% | 2026-02-08 |  |
| 16 | [0x1ff26f9f](https://polymarket.com/profile/0x1ff26f9f8a048d4f6fb2e4283f32f6ca64d2dbbd) | 27 | 34 | 74% | $3.5M | +46.7% (2.7) | -1.0% (-2.8) | -0.7% (-1.5) | moneyline 77% | 2026-01-25 |  |
| 17 | [0xe542afd3](https://polymarket.com/profile/0xe542afd3881c4c330ba0ebbb603bb470b2ba0a37) | 26 | 27 | 67% | $85k | +3.7% (2.6) | +7.4% (2.3) | +3.0% (2.0) | moneyline 99% | 2026-10-18 |  |
| 18 | [0xc2a37f1e](https://polymarket.com/profile/0xc2a37f1eb84fcc156c8aece9105dc1a73a36c3a6) | 43 | 44 | 80% | $592k | +15.5% (2.6) | -1.5% (-6.9) | -0.5% (-2.0) | moneyline 98% | 2025-11-07 |  |
| 19 | [0xe18ecc34](https://polymarket.com/profile/0xe18ecc345e00ee7c4f2d1f676f3dd2acb112f826) | 27 | 51 | 73% | $929k | +38.3% (2.6) | -1.4% (-1.7) | -1.2% (-1.2) | spread 69% | 2026-10-25 |  |
| 20 | [0xc383e03d](https://polymarket.com/profile/0xc383e03d31ff8ad22ff3c8d0e9462e9cbacaa540) | 106 | 148 | 60% | $9k | +21.5% (2.5) | +1.0% (1.0) | +0.3% (0.6) | spread 44% | 2026-02-08 |  |
| 21 | [0x814ca2f4](https://polymarket.com/profile/0x814ca2f44e953d6f564e873b62c2f1e18e557ffa) | 77 | 77 | 71% | $154k | +0.1% (2.5) | -0.6% (-2.2) | -0.0% (-0.8) | moneyline 100% | 2026-02-08 |  |
| 22 | [0x089d01d4](https://polymarket.com/profile/0x089d01d4d56621827ea57c098813337630b5c7c9) | 42 | 51 | 67% | $9k | +19.1% (2.5) | -1.6% (-4.6) | -1.2% (-3.2) | moneyline 91% | 2026-02-08 |  |
| 23 | [0xa3d38f81](https://polymarket.com/profile/0xa3d38f810aa438533f1abfd7510e1b130126f2bc) | 47 | 53 | 62% | $31k | +19.2% (2.4) | +0.7% (2.3) | +0.1% (0.1) | moneyline 70% | 2026-02-08 |  |
| 24 | [0xb5aa9120](https://polymarket.com/profile/0xb5aa9120ee3313e44d5e6a4895b8f7118cda5bd7) | 27 | 29 | 72% | $37k | +33.6% (2.4) | -1.4% (-4.8) | -1.0% (-3.3) | moneyline 94% | 2026-10-13 |  |
| 25 | [0x82147e52](https://polymarket.com/profile/0x82147e52ff6f18d3d55d98f59f260ee5be5aef72) | 30 | 39 | 62% | $18k | +39.8% (2.4) | -1.2% (-1.6) | -0.4% (-0.3) | moneyline 46% | 2026-02-08 |  |
| 26 | [0x5bf68500](https://polymarket.com/profile/0x5bf68500605ea3612a4768260b4af0c8d3a95200) | 27 | 27 | 63% | $44k | +50.0% (2.4) | -0.9% (-1.7) | +0.1% (0.2) | moneyline 100% | 2026-01-25 |  |
| 27 | [0x18670d5a](https://polymarket.com/profile/0x18670d5a83b7b38d509398067c095d4c321992ca) | 67 | 76 | 62% | $198k | +21.4% (2.4) | +0.9% (2.0) | +0.3% (1.3) | moneyline 63% | 2026-02-08 |  |
| 28 | [0xcf6c5492](https://polymarket.com/profile/0xcf6c5492124794394dd9eac46498a8babbe47e66) | 72 | 87 | 63% | $1.1M | +16.0% (2.3) | -0.7% (-1.2) | -0.6% (-2.0) | moneyline 48% | 2026-10-25 |  |
| 29 | [0x6141759f](https://polymarket.com/profile/0x6141759f8f3a7025ee1b6dff5dcd9f6d7655ded2) | 22 | 23 | 61% | $66k | +8.3% (2.3) | -1.0% (-1.3) | +0.4% (0.7) | moneyline 100% | 2026-02-08 |  |
| 30 | [0xc9c8f269](https://polymarket.com/profile/0xc9c8f269315019111c3c081072db26194d1e44fb) | 37 | 82 | 65% | $60k | +31.8% (2.3) | +0.1% (0.5) | -1.3% (-1.8) | moneyline 48% | 2026-10-11 |  |

## Caveats

* The close and the copy price come from the trade tape, not order books (Polymarket keeps no historical books), so they mix bid and ask prints. Thin alternate lines have noisy closes.
* Fills priced below 3c or above 97c, and fills after a market closed, are left out: they carry no information about skill.
* In-game (live) bets have no closing line, so they count only through Live P&L and do not affect the rank.
* A wallet can be one person with several wallets, or a bot. Maker share near 100% usually means a market maker earning the spread, which is not copyable even when CLV is positive.
