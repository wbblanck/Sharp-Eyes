# Tennis research

Everything behind the tennis findings, one folder per question. The reports
themselves live in the project files (`sharp-traders/tennis/`); each folder
here names its report. None of this needs a server: download the history once
with `sharp-eyes history-fetch --sport tennis` and run the scripts on a laptop.

| Folder | Question | Short answer so far |
|---|---|---|
| [`tiers/`](tiers/) | Which wallets are profitable per market (Tier 1/2/3), and can they be copied? | Tier 1-2 stay profitable more often than others, but copying them loses after fees (6 Nov 2026) |
| [`signal/`](signal/) | Does a wallet's trade predict the next price move? | Some do, but about 85% of the move is done within 5 s (7 Nov 2026) |
| [`pick-skill/`](pick-skill/) | Do list wallets pick better than their own price? | No wallet shows copyable pick skill (6 Nov 2026) |
| [`paper-test/`](paper-test/) | Copying the frozen list live, $5 a bet, 29 Oct to 26 Nov 2026 | Loses at both 30 s and 2 min once priced off the real order book |
| [`random-benchmark/`](random-benchmark/) | Do our lists beat random wallets with similar activity? | Not once 50-50 settlements and a few big wallets are removed (12 Nov 2026) |

The live Discord alerts are in [`alerts/`](../../alerts/). The download and
scoring code is `src/sharp_eyes/history/` ([docs/sharp-history.md](../../docs/sharp-history.md)).

Kept out of this public repo on purpose: the frozen wallet list, the watch
group, the Discord webhook and all downloaded data. Scripts that need a wallet
list take it as an argument or read a git-ignored file next to them.
