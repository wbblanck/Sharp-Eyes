# Phase 1: settlement templates and copyability

Phase 1 answers one question with captured data: **when a Polymarket NFL
trader places a wager, what could a follower actually have bought on
Polymarket US, Kalshi or Novig, seconds later, after fees, and was that price
any good?** It builds three pieces on top of the Phase 0 capture and wires them
into a report:

1. Settlement templates: the reviewed contract terms of every core NFL market
   type on every venue (`src/sharp_eyes/taxonomy/templates.py`).
2. A cross-venue matcher that turns every listing into buy options on a
   canonical proposition (`src/sharp_eyes/matching/nfl.py`).
3. Copyability scoring: wagers from fills, a depth-aware simulated buy against
   the captured book, taker fees and closing-line value
   (`src/sharp_eyes/copyability/`, `src/sharp_eyes/pricing/fees.py`).

```bash
uv run sharp-eyes copyability-report --hours 72            # Markdown to stdout
uv run sharp-eyes copyability-report --format json --out docs/reports/copyability.json
```

Scope follows the spec audit: Polymarket is the signal source only (rec. 1),
pre-game full-game moneyline, spread and total only (rec. 4), and paper mode
only.

## Settlement templates (audit rec. 7)

A venue lists hundreds of NFL markets a week but only a few market *types*,
and every listing of a type settles under the same terms. Each type's terms
were read once from the venue's own rules on 2026-10-24 and written down as a
versioned `SettlementTemplate`. No listing's free text is parsed to decide a
payout.

| Venue | Types | Rules source |
|---|---|---|
| Polymarket | `moneyline`, `spreads`, `totals`, `team_totals`, `first_half_moneyline` | Market `description` |
| Polymarket US | `football_team_full_game_winner` (v1, v2), `_spread`, `_total`, `football_team_points_full_game_total` | Market `description` |
| Kalshi | `KXNFLGAME`, `KXNFLSPREAD`, `KXNFLTOTAL` | CFTC contract terms (FOOTBALLGAMEWIN, FOOTBALLSPREAD, FOOTBALLTOTALS PDFs) |
| Novig | `MONEY`, `SPREAD`, `TOTAL` | Ludlow Exchange NFL series terms |

What the venues agree on: overtime counts everywhere, and a tied moneyline
pays $0.50 per side everywhere. Where they differ is the contingencies:

| | Postponed game | Cancelled game |
|---|---|---|
| Polymarket | Stays open until played | Resolves 50-50 |
| Polymarket US | Stands if played within two weeks (older moneylines) or two days; otherwise last fair price | Last fair price |
| Kalshi | Stands if played within 48 h; otherwise last fair price | Last fair price |
| Novig | Stands if played within 48 h; otherwise void at fair value | Fair value |

Kalshi spreads and totals are "wins by more than X" and "more than X", so a
result landing on a whole-number line loses rather than pushes. All core
lines captured so far are half-points, which cannot land.

**Drift detection.** Each template lists phrases the listing's rules text must
contain. When a venue rewords its rules, the listing gets `RULES_DRIFT`
instead of stale terms, and the type needs a fresh review and a new version.
This fired on the first live run: Polymarket US's newest winner listing
switched from a two-week to a two-day reschedule window. That is now
`football_team_full_game_winner@v2`; older listings still attach to v1.
Attachment tries each reviewed version, newest first.

**Match states.** Comparing a source listing's terms with a target's gives:

* `EXACT`: identical economic terms (Kalshi and Novig).
* `EQUIVALENT_WITH_RULE_DIFFERENCE`: identical except postponement or
  cancellation handling. This covers every Polymarket-to-execution-venue match,
  because Polymarket keeps postponed games open indefinitely.
* `NOT_EQUIVALENT`: a known material difference (e.g. overtime).
* `AMBIGUOUS`: a material term unknown on either side.

## Matching

`OptionIndex.build(events, markets)` resolves every listing to a
`Proposition(game, bet_type, period, pick, line)` and records each way to buy
it as a `BuyOption(venue, book_key, side)`. `LONG` buys the listed book's asks
and `SHORT` buys the other side of a YES/NO contract at 1 − bid. Each venue
encodes the proposition differently:

* Polymarket: one token per outcome; the spread line belongs to the first
  outcome, and that outcome must be the team named in "Spread: Team (−X)".
* Kalshi: the team code is in the ticker suffix. "PIT wins by more than 3.5"
  is PIT −3.5 as YES and the opponent +3.5 as NO. A total is Over as YES.
* Polymarket US: `marketSides[long]` names the team and its signed line. The
  short side is the opposite proposition.
* Novig: outcome names such as `PIT -3.5` and `Over 44.5`.

Listings that don't resolve are listed with a reason, never guessed. On the
live catalog every core listing resolved.

**Checked on live prices.** With the books captured on 2026-10-24, 1,552
propositions were quoted on two or more venues (spread at most 10¢). No
venue's mid was ever more than 3¢ from the cross-venue median, and the mean
absolute deviation was 0.2 to 0.4¢. A flipped side or sign would show up as a
gap of about 50¢.

## Copyability scoring (audit recs. 2 and 3)

**Wagers.** A wallet's consecutive BUY fills on one outcome token, each
within `copyability.wager_window_seconds` (60 s) of the previous one, form one
wager, maker fills included. A SELL ends the run and is never a wager itself.
The copy signal is the *first* fill's detection time. Backfilled fills (no
`prev_poll_at`) are excluded, because their observation time records when we
backfilled them, not when a follower could have seen them.

**Follower price.** A follower acts `reaction_seconds` (5 s) after detection.
Every equivalent option on an execution venue is priced by walking the
captured book for the paper stake, in each venue's lot size, plus that venue's
taker fee:

| Venue | Taker fee per contract at price p | Notes |
|---|---|---|
| Polymarket | `feeSchedule.rate` × p(1−p) (0.03 on NFL) | From the market payload |
| Polymarket US | `feeCoefficient` × p(1−p) (0.0695) | Order total, banker's rounding to the cent |
| Kalshi | 0.07 × p(1−p) | Rounded up to $0.0001 |
| Novig | 0.06 × p(1−p), only while in-game | So zero pre-game |

The follower takes the cheapest fee-inclusive price among accepted match
states.

**Unscorable, not guessed.** Books are stored only when they change, so a
stored snapshot stands for "the book until the next change" only while polling
continued. A quote counts only if that venue's book job ran within two tier
intervals before the follow time with no failed sweep in the last interval,
and the tier interval (the worst-case staleness) is within
`max_quote_age_seconds`. Otherwise the wager is `UNSCORABLE` with a reason. It
never falls back to the trader's own price.

**Measures** (probability points; 0.01 = 1¢ per $1 contract):

* `slippage`: follower average price minus trader price.
* `slippage_with_fees`: the same, using the follower's fee-inclusive price.
* `follower_clv`: closing mid on the chosen venue minus the follower's
  fee-inclusive price. Positive means the copy beat the close.
* `trader_clv`: Polymarket closing mid minus trader price. This is a skill
  signal, not evidence that the wager can be copied.
* `copy_cost`: trader_clv minus follower_clv, i.e. how much of the trader's
  edge a follower loses.

The closing book is the last snapshot before kickoff, confirmed by a poll in
the final 10 minutes.

## First live run

The first run on 2026-10-24 covered 14 minutes of live capture on a quiet
Saturday, from 16:59 to 17:13 UTC, when the container restarted. The report
is in [reports/2026-10-24-copyability.md](reports/2026-10-24-copyability.md).

* 68 live-detected Polymarket fills formed 48 wagers. 15 of them were $100 or
  more, and all 15 were scored.
* Polymarket US offered the best price for 14 of them and Kalshi for 1.
* Before fees, the follower paid a mean of +0.4¢ more than the trader (median
  +0.75¢). With taker fees included, the gap was +2.1¢, and the follower paid
  more on every wager. At these prices, fees cost a follower more than the
  delay did.
* The detection delay from block time to first sighting had a median of 24 s
  and a p90 of 173 s.
* CLV is n/a because none of these games had kicked off.

This is far too small a sample to judge copyability. That needs at least one
full Sunday slate captured on Oracle, with CLV computed after kickoff.

## Known limits

* Kalshi team totals and all half and quarter markets have no templates yet,
  so they are left out of matching.
* Novig whole-line spread and total pushes are not stated in the filed terms;
  the tie rule stays unknown (AMBIGUOUS) for whole lines.
* Settlement-based returns (won or lost) are not computed yet. CLV is the
  measure for now.
* Polymarket US's public API has no trade tape, so a US follower's queue
  position is not modelled. Every venue is assumed to fill at the displayed
  depth.

## Open decision for Will

`copyability.accept_contingency_differences: true` lets the report score
matches that differ only in postponement or cancellation handling. Without it,
**no** Polymarket wager is copyable anywhere, because Polymarket keeps
postponed games open indefinitely. The risk config still requires `EXACT` for
any future automated execution. Keep this for research, or require EXACT
everywhere?
