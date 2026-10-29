"""Markdown and CSV output for the sharp-trader ranking."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sharp_eyes.history.analyze import History, Persistence, WalletStats

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
    return f"{bt.lower().replace('_', ' ')} {stake / total:.0%}"


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

    def to_markdown(self) -> str:
        h, ranked = self.history, self.ranked
        sharp = [s for s in ranked if s.sharp]
        copyable = [s for s in ranked if s.copyable]
        lines = [
            "# Sharp NFL traders on Polymarket",
            "",
            f"Games {_day(h.first)} to {_day(h.last)}: {h.games} settled NFL games, "
            f"{h.fills:,} fills, {len({r.wallet for r in h.rows}):,} wallets. "
            f"Ranked: {len(ranked):,} wallets with aggressive (taker) bets before kickoff "
            f"in at least {self.min_games} games and {_usd(self.min_stake)} staked "
            "pre-game.",
            "",
            f"* **Flagged sharp** (their taker bets beat the closing line, "
            f"false-discovery rate under 5%): "
            f"{len(sharp)}",
            f"* **Still worth copying** after a {self.copy_delay:.0f} s delay (sharp, and "
            f"the delayed price still beats the close with t >= 2): {len(copyable)}",
            f"* **Winning record** (profitable before kickoff and won more than "
            f"{self.min_win_rate:.0%} of bets, same game and stake floors): "
            f"{len(self.records)}",
            "",
            "Columns: **Taker CLV** is the average edge of the wallet's aggressive "
            "pre-game bets versus the closing price, per dollar staked (+2% means they "
            "bought 2% cheaper than the close); the rank uses its t-statistic. **All "
            "CLV** adds their resting limit orders, which pick up half the spread for "
            "free. **ROI** is the settled pre-game result after taker fees. **Copy CLV** "
            f"is the CLV a follower would get buying {self.copy_delay:.0f} s later, on "
            "all of the wallet's pre-game fills. t is the t-statistic, clustered by game; "
            "about 3 or more is unlikely to be luck. **Maker** is the share of stake "
            "filled as resting limit orders. **Live P&L** is the in-game result in "
            "dollars.",
            "",
        ]
        if self.persistence:
            p = self.persistence
            lines += [
                f"## Does it persist? Ranked on games before {_day(p.split)}, measured after",
                "",
                f"Ranking used {p.train_games} games; the check uses the "
                f"{p.test_games} games after. Rank correlation between earlier CLV t "
                f"and later taker CLV, over {p.compared} wallets active in both: "
                f"**{'n/a' if p.rank_corr is None else f'{p.rank_corr:.2f}'}**.",
                "",
                "| Group | Wallets active after | Stake after | Taker CLV after "
                "| All CLV after | ROI after | Win rate after | Copy CLV after |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
            for g in p.groups:
                lines.append(
                    f"| {g.label} | {g.wallets} | {_usd(g.stake)} | {_pct(g.taker_clv)} | "
                    f"{_pct(g.clv)} | {_pct(g.roi)} | {_rate(g.win_rate)} | "
                    f"{_pct(g.copy_clv)} |"
                )
            lines.append("")
        lines += [
            f"## Top {min(self.top, len(ranked))} by taker CLV t-statistic",
            "",
            "| # | Wallet | Games | Pre-game stake | Taker CLV (t) | All CLV | ROI (t) "
            "| Copy CLV (t) | Maker | Live P&L (games) | Main bet type | Last game | Flag |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
        ]
        for i, s in enumerate(ranked[: self.top], 1):
            flag = "copyable" if s.copyable else ("sharp" if s.sharp else "")
            lines.append(
                f"| {i} | [{s.wallet[:10]}]({PROFILE}{s.wallet}) | {s.games} | "
                f"{_usd(s.pre_stake)} | {_pct(s.taker_clv)} ({_t(s.taker_clv_t)}) | "
                f"{_pct(s.clv)} | "
                f"{_pct(s.roi)} ({_t(s.roi_t)}) | {_pct(s.copy_clv)} ({_t(s.copy_clv_t)}) | "
                f"{s.maker_share:.0%} | {_signed_usd(s.live_pnl)} ({s.live_games}) | "
                f"{main_bet_type(s)} | {_day(s.last)} | {flag} |"
            )
        lines += self._records_markdown()
        lines += [
            "",
            "## Caveats",
            "",
            "* The close and the copy price come from the trade tape, not order books "
            "(Polymarket keeps no historical books), so they mix bid and ask prints. "
            "Thin alternate lines have noisy closes.",
            "* Fills priced below 3c or above 97c, and fills after a market closed, are "
            "left out: they carry no information about skill.",
            "* In-game (live) bets have no closing line, so they count only through "
            "Live P&L and do not affect the rank.",
            "* A wallet can be one person with several wallets, or a bot. Maker share "
            "near 100% usually means a market maker earning the spread, which is not "
            "copyable even when CLV is positive.",
            "",
        ]
        return "\n".join(lines)

    def _records_markdown(self) -> list[str]:
        out = [
            "",
            f"## Winning record: ROI above zero and over {self.min_win_rate:.0%} of bets won",
            "",
            "A bet is the wallet's net pre-game position in one market. Win rate ignores "
            "the price paid (backing 80c favourites wins 80% and can still lose money), "
            "so read it with ROI and CLV. Sorted by ROI t-statistic.",
            "",
            "| # | Wallet | Games | Bets | Win rate | Pre-game stake | ROI (t) "
            "| Taker CLV (t) | Copy CLV (t) | Main bet type | Last game | Also CLV-sharp |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
        ]
        for i, s in enumerate(self.records[: self.top], 1):
            out.append(
                f"| {i} | [{s.wallet[:10]}]({PROFILE}{s.wallet}) | {s.games} | {s.bets} | "
                f"{_rate(s.win_rate)} | {_usd(s.pre_stake)} | {_pct(s.roi)} ({_t(s.roi_t)}) | "
                f"{_pct(s.taker_clv)} ({_t(s.taker_clv_t)}) | "
                f"{_pct(s.copy_clv)} ({_t(s.copy_clv_t)}) | {main_bet_type(s)} | "
                f"{_day(s.last)} | {'yes' if s.sharp else ''} |"
            )
        return out

    def to_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([
            "rank", "wallet", "profile", "games", "taker_games", "pre_stake", "pre_pnl",
            "taker_clv", "taker_clv_t", "q_value", "clv", "clv_t", "roi", "roi_t", "copy_clv",
            "copy_clv_t", "copy_roi", "maker_share", "live_games", "live_stake", "live_pnl",
            "bets", "wins", "win_rate", "winning_record", "main_bet_type",
            "first_game", "last_game", "sharp", "copyable",
        ])  # fmt: skip
        record = {s.wallet for s in self.records}
        # Ranked wallets first, then winning-record wallets the CLV rank left out.
        ranked = {s.wallet for s in self.ranked}
        rows = self.ranked + [s for s in self.records if s.wallet not in ranked]
        for i, s in enumerate(rows, 1):
            w.writerow([
                i, s.wallet, PROFILE + s.wallet, s.games, s.taker_games, round(s.pre_stake, 2),
                round(s.pre_pnl, 2), _r(s.taker_clv), _r(s.taker_clv_t), f"{s.q_value:.4g}",
                _r(s.clv), _r(s.clv_t), _r(s.roi), _r(s.roi_t), _r(s.copy_clv),
                _r(s.copy_clv_t), _r(s.copy_roi), round(s.maker_share, 3), s.live_games,
                round(s.live_stake, 2), round(s.live_pnl, 2), s.bets, s.wins,
                _r(s.win_rate), int(s.wallet in record), main_bet_type(s),
                _day(s.first), _day(s.last),
                int(s.sharp), int(s.copyable),
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
