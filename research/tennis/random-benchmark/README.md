# Random-wallet benchmark (12 Nov 2026)

Wallets are picked with our rules on bets before 3 Jul 2026, then compared
after that date with 2,000 random groups of wallets that have similar activity
(matched on average price paid and stake size or bet count). Report: project
files `sharp-traders/tennis/random-benchmark/`.

    uv run sharp-eyes history-fetch --sport tennis --min-volume 50000 --rate 40 --concurrency 16
    uv run python research/tennis/tiers/bets.py data/history-tennis bets.csv.gz
    uv run --with pandas python research/tennis/tiers/tiers.py bets.csv.gz pre/ --before 2026-07-03
    uv run --with pandas python research/tennis/random-benchmark/rw2.py bets.csv.gz pre/wallet-markets.csv rw2.json
    uv run --with pandas python research/tennis/random-benchmark/rw3.py bets.csv.gz pre/wallet-markets.csv rw3.json   # 50-50s left out
    uv run --with pandas python research/tennis/random-benchmark/dig2.py bets.csv.gz
    uv run --with pandas python research/tennis/random-benchmark/dig3.py bets.csv.gz frozen-list-2026-10-29.csv

The second argument is the tier list picked before the split. The 12 Nov run
used the saved one from the 6 Nov tier report (`forward-test-tiers-before-2026-07-03.csv`);
`tiers.py ... --before 2026-07-03` rebuilds it.
