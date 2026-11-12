# Tennis sharp tiers by market

Applies Will's Tier 1/2/3 definition per wallet per market (tour x pre-match/in-play x bet type).

    uv run sharp-eyes history-fetch --sport tennis --min-volume 50000 --rate 40 --concurrency 16
    uv run python research/tennis/tiers/bets.py data/history-tennis bets.csv.gz
    uv run --with pandas python research/tennis/tiers/tiers.py bets.csv.gz out/
    uv run --with pandas python research/tennis/tiers/tiers.py bets.csv.gz pre/ --before 2026-07-03
    uv run --with pandas python research/tennis/tiers/forward.py bets.csv.gz pre/wallet-markets.csv 2026-07-03

Rule definitions: `tier()` in tiers.py, explained in the 6 Nov 2026 report (project files, sharp-traders/tennis/tiers/). Also here: `base.py` (maker vs taker among tiered wallets), `copytest.py` + `copysum.py` (copying tiered wallets 30 s / 2 min late). `bets.py` also writes a `shares` column (average price = stake / shares), used by `../random-benchmark/`..
