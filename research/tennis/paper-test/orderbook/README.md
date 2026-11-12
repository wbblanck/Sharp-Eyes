# Order-book checks (PendulumFlow archive)

Archive: https://archive.pendulumflow.com/ (free, CC BY-NC 4.0, credit pendulumflow). v3.1 has one file per hour per category:
https://dl.pendulumflow.com/v3.1/YYYY-MM-DD/HH/YYYY-MM-DDTHH.sports.parquet (~130-170 MB). Checksums: https://archive.pendulumflow.com/v3.1/SHA256SUMS.txt
Rate limit: 40 requests / 10 s per IP; on HTTP 429 wait 60 s. Send a plain client name (User-Agent).
Columns: market = condition id bytes, asset_id = token id as 32-byte big-endian; event_type book / price_change / best_bid_ask / last_trade_price.
Needs `pip install duckdb`. Archive clock runs ~2-3 s ahead of data-api /v2/trades timestamps.

- event_trades.py EVENT_ID CONDITION_ID WALLET_PREFIX OUTCOME : data-api trades around a wallet's first buy
- book_window.py FILE CONDITION_ID TOKEN_ID T_LO T_HI : ask-side changes, best bid/ask and trades in a window

2026-11-04 results: Okamura Under 2.5 (31 Oct) copy at 07:29:37Z had only 5 shares at 12c, next ask 89c; Brunold-Krajci Krajci (1 Nov) ask was 50c the whole 07:31:12-07:32:13Z, the 13c print was 17 shares up for ~0.1 s at 07:32:13.
