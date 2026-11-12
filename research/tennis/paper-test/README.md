# Tennis paper test (29 Oct to 26 Nov 2026)

Copies the frozen list's pre-match picks at $5 a bet, 30 s and 2 min after the
sharp's first buy, fees included. Rules are in the `paper_test.py` docstring.

These are copies of the scripts that run the nightly report from the project
files (`sharp-traders/tennis/paper-test/`). That copy keeps running unchanged
until the test ends; the only difference here is that the watch-group wallets
are read from a git-ignored `watch-wallets.txt` instead of being written in the
code.

    uv run sharp-eyes history-fetch --sport tennis --since 2026-10-29 --data-dir data/paper-tennis
    uv run python research/tennis/paper-test/paper_test.py data/paper-tennis      # needs frozen-list-2026-10-29.csv here
    uv run --with duckdb python research/tennis/paper-test/orderbook/book_check.py # re-prices each copy off the order book

* `novig_listings.py`, `novig_tier2.py`: the Tier 2 line priced on Novig.
* `maker_line.py`: the resting-order line (11 Nov 2026).
* `discord_post.py`: posts stdin to the Discord webhook in a git-ignored `.discord-webhook` file.
