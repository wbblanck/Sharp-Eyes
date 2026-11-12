# Tennis signal test (7 Nov 2026)

Does a wallet's trade predict the price move 5 s to 2 min later, and can a follower profit?
Report: project files sharp-traders/tennis/signal/signal-test-2026-11-07.md.

    uv run sharp-eyes history-fetch --sport tennis --min-volume 50000 --rate 40 --concurrency 16
    uv run python scripts/tennis-signal/signals.py data/history-tennis data/signals.csv.gz
    uv run --with pandas --with numpy python scripts/tennis-signal/classify.py data/signals.csv.gz TIERS.csv OUT [--before|--after DATE]
    uv run --with pandas --with numpy python scripts/tennis-signal/pooled.py data/signals.csv.gz OUT_BEFORE/wallet-markets.csv 2026-07-03 pooled.csv

Order-book check (PendulumFlow v3.1 archive, free, CC BY-NC 4.0, credit pendulumflow):

    uv run --with duckdb python scripts/tennis-signal/book_fetch.py data/book TMP
    uv run python scripts/tennis-signal/tokens.py CIDS.txt data/tokens.json
    uv run --with duckdb --with numpy --with pandas python scripts/tennis-signal/offset.py data/history-tennis data/tokens.json data/book
    uv run --with duckdb --with numpy --with pandas python scripts/tennis-signal/book_signals.py data/signals.csv.gz data/tokens.json data/book -3.5 book-signals.csv.gz
    uv run --with pandas --with numpy python scripts/tennis-signal/book_compare.py book-signals.csv.gz OUT_BEFORE/wallet-markets.csv book-compare.csv
