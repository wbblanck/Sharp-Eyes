"""Markdown and CSV output for the sharp-trader ranking."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sharp_eyes.history.analyze import MARK_HORIZON, History, Persistence, WalletStats

PROFILE = "https://polymarket.com/profile/"


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d")


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def _t(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1f}"


def _usd(x: float) -> str:
    return f"${x / 1e6:.1f}M" if abs(x) >= 1e6 else f"${x / 1e3:.0f}k"


def _signed_usd(x: float) -> str:
    return ("-" if x < 0 else "+") + _usd(abs(x))


def main_bet_type(s: WalletStats) -> str:
    if not s.bet_types:
        return ""
    total = sum(v[0] for v in s.bet_types.values()) or 1
    bt, (stake, _) = max(s.bet_types.items(), key=lambda kv: kv[1][0])
    name = bt.lower().replace("tennis_", "").replace("_", " ")
    return f"{name} {stake / total:.0%}"


@dataclass(frozen=True)
class Words:
    sport: str
    game: str
    games: str
    start: str
    pre: str
    live: str


WORDS = {
    "nfl": Words("NFL", "game", "games", "kickoff", "pre-game", "in-game"),
    "tennis": Words("tennis", "match", "matches", "the match starts", "pre-match", "in-play"),
}


@dataclass
class SharpReport:
    history: History
    ranked: list[WalletStats]
    persistence: Persistence | None
    min_games: int
    min_stake: float
    copy_delay: float
    top: int = 30
    records: list[WalletStats] = field(default_factory=list)
    min_win_rate: float = 0.60
    sport: str = "nfl"
    live_ranked: list[WalletStats] = field(default_factory=list)

    @property
    def w(self) -> Words:
        return WORDS[self.sport]

    def to_markdown(self) -> str:
        h, ranked, w = self.history, self.ranked, self.w
        sharp = [s for s in ranked if s.sharp]
        copyable = [s for s in ranked if s.copyable]
        lines = [
            f"# Sharp {w.sport} traders on Polymarket",
            "",
            f"{w.games.capitalize()} {_day(h.first)} to {_day(h.last)}: {h.games:,} settled "
            f"{w.sport} {w.games}, {h.fills:,} fills, {len({r.wallet for r in h.rows}):,} "
            f"wallets. Ranked: {len(ranked):,} wallets with aggressive (taker) bets before "
            f"{w.start} in at least {self.min_games} {w.games} and {_usd(self.min_stake)} "
            f"staked {w.pre}.",
            "",
            f"* **Flagged sharp** (their taker bets beat the closing line, "
            f"false-discovery rate under 5%): {len(sharp)}",
            f"* **Still worth copying** after a {self.copy_delay:.0f} s delay (sharp, and "
            f"the delayed price still beats the close with t >= 2): {len(copyable)}",
            f"* **Winning record** (profitable {w.pre} and won more than "
            f"{self.min_win_rate:.0%} of bets, same {w.game} and stake floors): "
            f"{len(self.records)}",
        ]
        if self.live_ranked:
            live_sharp = [s for s in self.live_ranked if s.live_sharp]
            lines += [
                f"* **{w.live.capitalize()} sharp** (price moves their way in the "
                f"{MARK_HORIZON // 60} minutes after their {w.live} taker bets, false-discovery "
                f"rate under 5%, of {len(self.live_ranked):,} wallets with {self.min_games}+ "
                f"{w.games} and {_usd(self.min_stake)} {w.live}): {len(live_sharp)}, of which "
                f"{sum(s.live_copyable for s in live_sharp)} keep the edge with a "
                f"{self.copy_delay:.0f} s delay",
            ]
        lines += [
            "",
            f"Columns: **Taker CLV** is the average edge of the wallet's aggressive {w.pre} "
            "bets versus the closing price, per dollar staked (+2% means they bought 2% "
            "cheaper than the close); the rank uses its t-statistic. **All CLV** adds their "
            "resting limit orders, which pick up half the spread for free. **ROI** is the "
            f"settled {w.pre} result after taker fees. **Copy CLV** is the CLV a follower "
            f"would get buying {self.copy_delay:.0f} s later, on all of the wallet's {w.pre} "
            "fills; **after fees** subtracts the follower's taker fee. t is the t-statistic, "
            f"clustered by {w.game}; about 3 or more is unlikely to be luck. **Maker** is the "
            f"share of stake filled as resting limit orders. **Live P&L** is the {w.live} "
            "result in dollars.",
            "",
        ]
        if self.persistence:
            lines += self._persistence_markdown(self.persistence)
        lines += [
            f"## Top {min(self.top, len(ranked))} {w.pre} by taker CLV t-statistic",
            "",
            f"| # | Wallet | {w.games.capitalize()} | {w.pre.capitalize()} stake "
            "| Taker CLV (t) | All CLV | ROI (t) | Copy CLV (t) | Copy after fees | Maker "
            f"| Live P&L ({w.games}) | Main bet type | Last {w.game} | Flag |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
        ]
        for i, s in enumerate(ranked[: self.top], 1):
            flag = "copyable" if s.copyable else ("sharp" if s.sharp else "")
            lines.append(
                f"| {i} | [{s.wallet[:10]}]({PROFILE}{s.wallet}) | {s.games} | "
                f"{_usd(s.pre_stake)} | {_pct(s.taker_clv)} ({_t(s.taker_clv_t)}) | "
                f"{_pct(s.clv)} | "
                f"{_pct(s.roi)} ({_t(s.roi_t)}) | {_pct(s.copy_clv)} ({_t(s.copy_clv_t)}) | "
                f"{_pct(s.copy_net)} | "
                f"{s.maker_share:.0%} | {_signed_usd(s.live_pnl)} ({s.live_games}) | "
                f"{main_bet_type(s)} | {_day(s.last)} | {flag} |"
            )
        lines += self._records_markdown()
        if self.live_ranked:
            lines += self._live_markdown()
        lines += [
            "",
            "## Caveats",
            "",
            "* The close and the copy price come from the trade tape, not order books "
            "(Polymarket keeps no historical books), so they mix bid and ask prints. "
            "Thin alternate lines have noisy closes.",
            f"* {w.pre.capitalize()} fills priced below 3c or above 97c, and fills after a "
            "market closed, are left out: they carry no information about skill.",
            f"* {w.live.capitalize()} bets have no closing line, so they do not affect the "
            f"{w.pre} rank; they are scored on the price {MARK_HORIZON // 60} minutes later "
            "instead.",
            "* A wallet can be one person with several wallets, or a bot. Maker share "
            "near 100% usually means a market maker earning the spread, which is not "
            "copyable even when CLV is positive.",
        ]
        if self.sport == "tennis":
            lines.append(
                "* Match start times are Polymarket's listed times. When the moneyline "
                "swings like live play in the hour before the listed start, the match is "
                "treated as started at that swing."
            )
        lines.append("")
        return "\n".join(lines)

    def _persistence_markdown(self, p: Persistence) -> list[str]:
        w = self.w
        out = [
            f"## Does it persist? Ranked on {w.games} before {_day(p.split)}, measured after",
            "",
            f"Ranking used {p.train_games:,} {w.games}; the check uses the "
            f"{p.test_games:,} {w.games} after. Rank correlation between earlier CLV t "
            f"and later taker CLV, over {p.compared} wallets active in both: "
            f"**{'n/a' if p.rank_corr is None else f'{p.rank_corr:.2f}'}**.",
            "",
            "| Group | Wallets active after | Stake after | Taker CLV after "
            "| All CLV after | ROI after | Win rate after | Copy CLV after "
            "| Copy after fees |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for g in p.groups:
            out.append(
                f"| {g.label} | {g.wallets} | {_usd(g.stake)} | {_pct(g.taker_clv)} | "
                f"{_pct(g.clv)} | {_pct(g.roi)} | {_rate(g.win_rate)} | "
                f"{_pct(g.copy_clv)} | {_pct(g.copy_net)} |"
            )
        out.append("")
        if p.live_groups:
            out += [
                f"### {w.live.capitalize()}: ranked on markout before {_day(p.split)}, "
                "measured after",
                "",
                f"Rank correlation over {p.live_compared} wallets: "
                f"**{'n/a' if p.live_rank_corr is None else f'{p.live_rank_corr:.2f}'}**.",
                "",
                f"| Group | Wallets active after | {w.live.capitalize()} stake after "
                "| Markout after | Copy markout after | Copy after fees |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            for g in p.live_groups:
                out.append(
                    f"| {g.label} | {g.live_wallets} | {_usd(g.live_stake)} | "
                    f"{_pct(g.live_mark)} | {_pct(g.live_copy)} | {_pct(g.live_copy_net)} |"
                )
            out.append("")
        return out

    def _records_markdown(self) -> list[str]:
        w = self.w
        out = [
            "",
            f"## Winning record: ROI above zero and over {self.min_win_rate:.0%} of bets won",
            "",
            f"A bet is the wallet's net {w.pre} position in one market. Win rate ignores "
            "the price paid (backing 80c favourites wins 80% and can still lose money), "
            "so read it with ROI and CLV. Sorted by ROI t-statistic.",
            "",
            f"| # | Wallet | {w.games.capitalize()} | Bets | Win rate | {w.pre.capitalize()} "
            "stake | ROI (t) | Taker CLV (t) | Copy CLV (t) | Copy after fees "
            f"| Main bet type | Last {w.game} | Also CLV-sharp |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
        ]
        for i, s in enumerate(self.records[: self.top], 1):
            out.append(
                f"| {i} | [{s.wallet[:10]}]({PROFILE}{s.wallet}) | {s.games} | {s.bets} | "
                f"{_rate(s.win_rate)} | {_usd(s.pre_stake)} | {_pct(s.roi)} ({_t(s.roi_t)}) | "
                f"{_pct(s.taker_clv)} ({_t(s.taker_clv_t)}) | "
                f"{_pct(s.copy_clv)} ({_t(s.copy_clv_t)}) | {_pct(s.copy_net)} | "
                f"{main_bet_type(s)} | {_day(s.last)} | {'yes' if s.sharp else ''} |"
            )
        return out

    def _live_markdown(self) -> list[str]:
        w = self.w
        out = [
            "",
            f"## Top {min(self.top, len(self.live_ranked))} {w.live} by markout t-statistic",
            "",
            f"**Markout** is how far the price moved in the bettor's favour "
            f"{MARK_HORIZON // 60} minutes after their {w.live} taker bets, per dollar. "
            f"**Copy markout** is the same for a follower buying {self.copy_delay:.0f} s "
            "later. Live prices jump on every point, so only a big t means anything.",
            "",
            f"| # | Wallet | {w.live.capitalize()} {w.games} | {w.live.capitalize()} stake "
            "| Markout (t) | Copy markout (t) | Copy after fees | Live P&L | Maker "
            f"| Last {w.game} | Flag |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
        for i, s in enumerate(self.live_ranked[: self.top], 1):
            flag = "copyable" if s.live_copyable else ("sharp" if s.live_sharp else "")
            out.append(
                f"| {i} | [{s.wallet[:10]}]({PROFILE}{s.wallet}) | {s.live_taker_games} | "
                f"{_usd(s.live_stake)} | {_pct(s.live_mark)} ({_t(s.live_mark_t)}) | "
                f"{_pct(s.live_copy)} ({_t(s.live_copy_t)}) | {_pct(s.live_copy_net)} | "
                f"{_signed_usd(s.live_pnl)} | {s.maker_share:.0%} | {_day(s.last)} | {flag} |"
            )
        return out

    def to_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([
            "rank", "wallet", "profile", "games", "taker_games", "pre_stake", "pre_pnl",
            "taker_clv", "taker_clv_t", "q_value", "clv", "clv_t", "roi", "roi_t", "copy_clv",
            "copy_clv_t", "copy_roi", "copy_net_of_fees", "maker_share", "live_games",
            "live_stake", "live_pnl", "live_taker_games", "live_markout", "live_markout_t",
            "live_q_value", "live_copy_markout", "live_copy_markout_t", "live_copy_net_of_fees",
            "bets", "wins", "win_rate", "winning_record", "main_bet_type",
            "first_game", "last_game", "sharp", "copyable", "live_sharp", "live_copyable",
        ])  # fmt: skip
        record = {s.wallet for s in self.records}
        # Ranked wallets first, then winning-record and live-ranked wallets left out.
        rows: list[WalletStats] = []
        seen: set[str] = set()
        for s in [*self.ranked, *self.records, *self.live_ranked]:
            if s.wallet not in seen:
                seen.add(s.wallet)
                rows.append(s)
        for i, s in enumerate(rows, 1):
            w.writerow([
                i, s.wallet, PROFILE + s.wallet, s.games, s.taker_games, round(s.pre_stake, 2),
                round(s.pre_pnl, 2), _r(s.taker_clv), _r(s.taker_clv_t), f"{s.q_value:.4g}",
                _r(s.clv), _r(s.clv_t), _r(s.roi), _r(s.roi_t), _r(s.copy_clv),
                _r(s.copy_clv_t), _r(s.copy_roi), _r(s.copy_net), round(s.maker_share, 3),
                s.live_games, round(s.live_stake, 2), round(s.live_pnl, 2), s.live_taker_games,
                _r(s.live_mark), _r(s.live_mark_t), f"{s.live_q_value:.4g}", _r(s.live_copy),
                _r(s.live_copy_t), _r(s.live_copy_net),
                s.bets, s.wins, _r(s.win_rate), int(s.wallet in record), main_bet_type(s),
                _day(s.first), _day(s.last),
                int(s.sharp), int(s.copyable), int(s.live_sharp), int(s.live_copyable),
            ])  # fmt: skip
        return buf.getvalue()


def _rate(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def _r(x: float | None) -> str:
    return "" if x is None else f"{x:.4f}"


def default_split(rows_kickoffs: Sequence[float]) -> float | None:
    """Midpoint in time order: rank on the first half of games, test on the second."""
    if not rows_kickoffs:
        return None
    ordered = sorted(set(rows_kickoffs))
    return ordered[len(ordered) // 2]
