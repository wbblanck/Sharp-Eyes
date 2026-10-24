"""Exact contract matching for NFL full-game moneyline, spread and total (first milestone).

Every captured listing is reduced to the *propositions* it lets a buyer hold,
in venue-neutral terms: "PIT wins", "PIT covers -3.5", "over 44.5". Two buy
options on different venues are the same bet exactly when they name the same
proposition on the same game and their reviewed settlement rules agree.

* A game is identified by its two teams (canonical keys from the explicit alias
  table, never fuzzy matching) and its US Eastern calendar date.
* A spread proposition carries the handicap applied to the picked team:
  "PIT covers -3.5" pays when PIT wins by more than 3.5.
* TWO_WAY venues (Polymarket, Novig) list one book per outcome, so each book is
  one LONG option. YES_NO venues (Kalshi, Polymarket US) list one contract per
  proposition; its YES is a LONG option and its NO a SHORT option on the
  opposite proposition, bought at 1 - the YES bid.

Listings that cannot be resolved unambiguously (an unknown team name, a missing
template, rules drift) produce no options and an ``Unresolved`` record saying
why, so coverage can be audited instead of silently shrinking.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from sharp_eyes.capture.records import BetType, CaptureVenue, EventRecord, MarketRecord, Period
from sharp_eyes.domain import MatchState
from sharp_eyes.normalization.participants import ParticipantRegistry
from sharp_eyes.normalization.seeds import seeded_registry
from sharp_eyes.taxonomy.categories import Sport
from sharp_eyes.taxonomy.settlement import SettlementRules, rule_differences
from sharp_eyes.taxonomy.templates import AttachStatus, attach_template

MATCHER_VERSION = "nfl-core-1"

OVER, UNDER = "OVER", "UNDER"
_EASTERN = ZoneInfo("America/New_York")
_TENTH = Decimal("0.1")
_CORE = frozenset({BetType.MONEYLINE, BetType.SPREAD, BetType.TOTAL})

# Rule terms that only matter if the game is not played normally (postponed,
# cancelled, abandoned). Contracts that differ only here pay identically on
# every game that is actually played to a result.
CONTINGENCY_TERMS = frozenset(
    {"postponement", "postponement_window_hours", "cancellation", "cancellation_price"}
)


class Side(StrEnum):
    LONG = "LONG"  # Buy the book's own outcome: walk its asks
    SHORT = "SHORT"  # Buy the complement (NO): pay 1 - each bid


@dataclass(frozen=True, order=True)
class Proposition:
    game: str  # "NFL|<eastern date>|<team>|<team>", teams sorted
    bet_type: BetType
    period: Period
    pick: str  # Canonical team key, or OVER / UNDER
    line: Decimal | None = None  # Handicap on ``pick`` (spreads) or the total

    def __post_init__(self) -> None:
        if self.line is not None:  # One spelling per line: 3.50 and 3.5 print alike
            object.__setattr__(self, "line", self.line.quantize(_TENTH))

    def __str__(self) -> str:
        line = (
            ""
            if self.line is None
            else f" {self.line:+}"
            if self.bet_type is BetType.SPREAD
            else f" {self.line}"
        )
        return f"{self.game} {self.bet_type}/{self.period} {self.pick}{line}"  # fmt: skip


@dataclass(frozen=True)
class BuyOption:
    proposition: Proposition
    venue: CaptureVenue
    market_id: str
    book_key: str
    side: Side
    rules: SettlementRules
    template_key: str
    kickoff: datetime | None
    raw: Mapping[str, Any] = field(default_factory=dict, compare=False, hash=False, repr=False)


@dataclass(frozen=True)
class Unresolved:
    venue: CaptureVenue
    market_id: str
    reason: str


def game_key(teams: Iterable[str], day: date) -> str:
    a, b = sorted(teams)
    return f"NFL|{day.isoformat()}|{a}|{b}"


def eastern_date(ts: datetime) -> date:
    return ts.astimezone(_EASTERN).date()


def classify_match(
    source: SettlementRules, target: SettlementRules
) -> tuple[MatchState, list[str]]:
    """Match state for two options on the same proposition, from their rules alone."""
    diffs = rule_differences(source, target)
    if not diffs:
        return MatchState.EXACT, diffs
    material = [d for d in diffs if d.split(":")[0] not in CONTINGENCY_TERMS]
    if not material:
        return MatchState.EQUIVALENT_WITH_RULE_DIFFERENCE, diffs
    if any(d.endswith(":unknown") for d in material):
        return MatchState.AMBIGUOUS, diffs
    return MatchState.NOT_EQUIVALENT, diffs


def _dec(value: Any) -> Decimal | None:
    try:
        return None if value is None or value == "" else Decimal(str(value))
    except InvalidOperation:
        return None


def _flip(prop: Proposition, teams: frozenset[str]) -> Proposition:
    """The proposition that pays exactly when ``prop`` does not."""
    if prop.bet_type is BetType.TOTAL:
        pick = UNDER if prop.pick == OVER else OVER
        return Proposition(prop.game, prop.bet_type, prop.period, pick, prop.line)
    (other,) = teams - {prop.pick}
    line = None if prop.line is None else -prop.line
    return Proposition(prop.game, prop.bet_type, prop.period, other, line)


class _Resolver:
    def __init__(self, registry: ParticipantRegistry) -> None:
        self.registry = registry

    def team(self, text: str | None) -> str | None:
        return self.registry.resolve(Sport.NFL, text) if text else None

    def teams(self, names: Sequence[str | None]) -> frozenset[str] | None:
        keys = [self.team(n) for n in names]
        if len(keys) != 2 or None in keys or keys[0] == keys[1]:
            return None
        return frozenset(k for k in keys if k)


_SPLIT = re.compile(r"\s+(?:vs\.?|@|at)\s+", re.IGNORECASE)
_PM_SPREAD = re.compile(r"^Spread: (.+?) \(")
_KALSHI_DATE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})")
_MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
)}  # fmt: skip


class OptionIndex:
    """Buy options for every resolvable core listing in a catalog."""

    def __init__(self, registry: ParticipantRegistry | None = None) -> None:
        self._r = _Resolver(registry or seeded_registry())
        self.options: list[BuyOption] = []
        self.unresolved: list[Unresolved] = []
        self._by_prop: dict[Proposition, list[BuyOption]] = defaultdict(list)
        self._by_book: dict[tuple[CaptureVenue, str, Side], BuyOption] = {}

    # -- lookups -----------------------------------------------------------

    def option(
        self, venue: CaptureVenue, book_key: str, side: Side = Side.LONG
    ) -> BuyOption | None:
        return self._by_book.get((venue, book_key, side))

    def equivalents(self, prop: Proposition) -> list[BuyOption]:
        return list(self._by_prop.get(prop, ()))

    # -- building ----------------------------------------------------------

    @classmethod
    def build(
        cls,
        events: Iterable[EventRecord],
        markets: Iterable[MarketRecord],
        registry: ParticipantRegistry | None = None,
    ) -> OptionIndex:
        index = cls(registry)
        events_by_id = {(e.venue, e.event_id): e for e in events}
        markets = list(markets)
        kalshi_games = index._kalshi_games(markets)
        for m in markets:
            if not m.is_core or m.bet_type not in _CORE:
                continue
            event = events_by_id.get((m.venue, m.event_id))
            try:
                found = index._options(m, event, kalshi_games)
            except _Skip as skip:
                index.unresolved.append(Unresolved(m.venue, m.market_id, str(skip)))
                continue
            for opt in found:
                index._add(opt)
        return index

    def _add(self, opt: BuyOption) -> None:
        self.options.append(opt)
        self._by_prop[opt.proposition].append(opt)
        self._by_book[(opt.venue, opt.book_key, opt.side)] = opt

    def _kalshi_games(self, markets: Sequence[MarketRecord]) -> dict[str, frozenset[str]]:
        """Kalshi game code (e.g. 26OCT25PITNO) -> teams, from the KXNFLGAME markets."""
        found: dict[str, set[str]] = defaultdict(set)
        for m in markets:
            if m.venue is CaptureVenue.KALSHI and m.venue_market_type == "KXNFLGAME":
                if team := self._r.team(m.market_id.rsplit("-", 1)[-1]) or self._r.team(
                    m.raw.get("yes_sub_title")
                ):
                    found[m.event_id.split("-", 1)[-1]].add(team)
        return {code: frozenset(t) for code, t in found.items() if len(t) == 2}

    def _options(
        self,
        m: MarketRecord,
        event: EventRecord | None,
        kalshi_games: Mapping[str, frozenset[str]],
    ) -> list[BuyOption]:
        attached = attach_template(m)
        if attached.status is not AttachStatus.ATTACHED:
            detail = "; ".join(attached.problems)
            raise _Skip(f"{attached.status}: {m.venue_market_type} {detail}".strip())
        assert attached.template is not None and attached.rules is not None
        if m.venue is CaptureVenue.KALSHI:
            code = m.event_id.split("-", 1)[-1]
            teams = kalshi_games.get(code)
            day = _kalshi_day(code)
        else:
            teams = self._event_teams(m.venue, event)
            start = m.start_time or (event.start_time if event else None)
            day = eastern_date(start) if start else None
        if teams is None:
            raise _Skip("teams not resolved")
        if day is None:
            raise _Skip("no game date")
        game = game_key(teams, day)
        pairs = self._propositions(m, game, teams)

        def make(prop: Proposition, book_key: str, side: Side) -> BuyOption:
            return BuyOption(
                prop, m.venue, m.market_id, book_key, side, attached.rules,  # type: ignore[arg-type]
                attached.template.key, m.start_time, m.raw,  # type: ignore[union-attr]
            )  # fmt: skip

        out = [make(p, k, Side.LONG) for p, k in pairs]
        if m.venue in (CaptureVenue.KALSHI, CaptureVenue.POLYMARKET_US):
            out += [make(_flip(p, teams), k, Side.SHORT) for p, k in pairs]
        return out

    def _event_teams(self, venue: CaptureVenue, event: EventRecord | None) -> frozenset[str] | None:
        if event is None:
            return None
        listed = event.raw.get("teams")
        if isinstance(listed, list) and len(listed) == 2:
            key = "abbreviation" if venue is CaptureVenue.POLYMARKET_US else "name"
            if found := self._r.teams([t.get(key) for t in listed if isinstance(t, dict)]):
                return found
        parts = _SPLIT.split(event.title.strip())
        return self._r.teams(parts) if len(parts) == 2 else None

    def _propositions(
        self, m: MarketRecord, game: str, teams: frozenset[str]
    ) -> list[tuple[Proposition, str]]:
        """(proposition, book_key) for each LONG option of the listing."""

        def prop(pick: str, line: Decimal | None) -> Proposition:
            return Proposition(game, m.bet_type, m.period, pick, line)

        def team(text: str | None) -> str:
            key = self._r.team(text)
            if key is None or key not in teams:
                raise _Skip(f"team {text!r} not resolved to this game")
            return key

        if m.bet_type is BetType.TOTAL:
            if m.line is None:
                raise _Skip("total without a line")
        if m.venue is CaptureVenue.POLYMARKET:
            return self._polymarket(m, prop, team)
        if m.venue is CaptureVenue.NOVIG:
            return self._novig(m, prop, team)
        if m.venue is CaptureVenue.KALSHI:
            return self._kalshi(m, prop, team)
        return self._polymarket_us(m, prop, team, teams)

    @staticmethod
    def _polymarket(m: MarketRecord, prop: Any, team: Any) -> list[tuple[Proposition, str]]:
        books = m.books
        if len(books) != 2:
            raise _Skip(f"{len(books)} outcomes")
        if m.bet_type is BetType.MONEYLINE:
            return [(prop(team(b.outcome), None), b.book_key) for b in books]
        if m.bet_type is BetType.SPREAD:
            if m.line is None:
                raise _Skip("spread without a line")
            # The line applies to the first outcome: "Spread: Seahawks (-0.5)".
            first, second = books
            named = _PM_SPREAD.match(m.title)
            if named is None or named.group(1) != first.outcome:
                raise _Skip(f"spread title {m.title!r} does not name the first outcome")
            return [
                (prop(team(first.outcome), m.line), first.book_key),
                (prop(team(second.outcome), -m.line), second.book_key),
            ]
        return [(prop(_over_under(b.outcome), m.line), b.book_key) for b in books]

    @staticmethod
    def _novig(m: MarketRecord, prop: Any, team: Any) -> list[tuple[Proposition, str]]:
        out = []
        for b in m.books:
            if m.bet_type is BetType.MONEYLINE:
                out.append((prop(team(b.outcome), None), b.book_key))
            elif m.bet_type is BetType.SPREAD:
                name, _, line = b.outcome.rpartition(" ")
                if (handicap := _dec(line)) is None:
                    raise _Skip(f"spread outcome {b.outcome!r}")
                out.append((prop(team(name), handicap), b.book_key))
            else:
                word = b.outcome.split(" ", 1)[0]
                out.append((prop(_over_under(word), m.line), b.book_key))
        if len(out) != 2:
            raise _Skip(f"{len(out)} outcomes")
        return out

    @staticmethod
    def _kalshi(m: MarketRecord, prop: Any, team: Any) -> list[tuple[Proposition, str]]:
        suffix = m.market_id.rsplit("-", 1)[-1]
        if m.bet_type is BetType.MONEYLINE:
            return [(prop(team(suffix), None), m.market_id)]
        if m.line is None:
            raise _Skip("no floor_strike")
        if m.bet_type is BetType.SPREAD:
            # "PIT wins by more than 20.5" is PIT covering -20.5.
            return [(prop(team(suffix.rstrip("0123456789")), -m.line), m.market_id)]
        return [(prop(OVER, m.line), m.market_id)]

    @staticmethod
    def _polymarket_us(
        m: MarketRecord, prop: Any, team: Any, teams: frozenset[str]
    ) -> list[tuple[Proposition, str]]:
        sides = [s for s in m.raw.get("marketSides") or [] if isinstance(s, dict)]
        long_side = next((s for s in sides if s.get("long")), None)
        if long_side is None or len(m.books) != 1:
            raise _Skip("no long side")
        book = m.books[0].book_key
        if m.bet_type is BetType.TOTAL:
            if str(long_side.get("description", "")).lower() != "over":
                raise _Skip(f"total long side {long_side.get('description')!r}")
            return [(prop(OVER, m.line), book)]
        abbr = (long_side.get("team") or {}).get("abbreviation")
        if m.bet_type is BetType.MONEYLINE:
            return [(prop(team(abbr), None), book)]
        handicap = _dec(str(long_side.get("description", "")).replace("+", ""))
        if handicap is None or m.line is None or abs(handicap) != abs(m.line):
            raise _Skip(f"spread long side {long_side.get('description')!r}")
        return [(prop(team(abbr), handicap), book)]


def _over_under(text: str) -> str:
    word = text.strip().upper()
    if word not in (OVER, UNDER):
        raise _Skip(f"total outcome {text!r}")
    return word


def _kalshi_day(code: str) -> date | None:
    m = _KALSHI_DATE.match(code)
    if not m or m.group(2) not in _MONTHS:
        return None
    return date(2000 + int(m.group(1)), _MONTHS[m.group(2)], int(m.group(3)))


class _Skip(Exception):
    """A listing that cannot be resolved unambiguously."""
