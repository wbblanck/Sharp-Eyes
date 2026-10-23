"""Seed participants for NFL and NBA teams.

Tennis players are open-ended and are added from venue data into the
``participants`` and ``participant_aliases`` tables as they are reviewed.

Each row is (abbreviation, city/region, nickname, extra aliases). The canonical
key is ``<SPORT>:<ABBR>``. City names that more than one team shares (Los
Angeles, New York) are added as aliases for every such team, so resolving them
alone is ambiguous and returns no match.
"""

from __future__ import annotations

from sharp_eyes.normalization.participants import Participant, ParticipantKind, ParticipantRegistry
from sharp_eyes.taxonomy.categories import Sport

_NFL: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("ARI", "Arizona", "Cardinals", ()),
    ("ATL", "Atlanta", "Falcons", ()),
    ("BAL", "Baltimore", "Ravens", ()),
    ("BUF", "Buffalo", "Bills", ()),
    ("CAR", "Carolina", "Panthers", ()),
    ("CHI", "Chicago", "Bears", ()),
    ("CIN", "Cincinnati", "Bengals", ()),
    ("CLE", "Cleveland", "Browns", ()),
    ("DAL", "Dallas", "Cowboys", ()),
    ("DEN", "Denver", "Broncos", ()),
    ("DET", "Detroit", "Lions", ()),
    ("GB", "Green Bay", "Packers", ("GNB",)),
    ("HOU", "Houston", "Texans", ()),
    ("IND", "Indianapolis", "Colts", ()),
    ("JAX", "Jacksonville", "Jaguars", ("JAC",)),
    ("KC", "Kansas City", "Chiefs", ("KAN",)),
    ("LV", "Las Vegas", "Raiders", ("LVR",)),
    ("LAC", "Los Angeles", "Chargers", ("LA Chargers",)),
    ("LAR", "Los Angeles", "Rams", ("LA Rams",)),
    ("MIA", "Miami", "Dolphins", ()),
    ("MIN", "Minnesota", "Vikings", ()),
    ("NE", "New England", "Patriots", ("NWE",)),
    ("NO", "New Orleans", "Saints", ("NOR",)),
    ("NYG", "New York", "Giants", ("NY Giants",)),
    ("NYJ", "New York", "Jets", ("NY Jets",)),
    ("PHI", "Philadelphia", "Eagles", ()),
    ("PIT", "Pittsburgh", "Steelers", ()),
    ("SF", "San Francisco", "49ers", ("SFO", "Niners")),
    ("SEA", "Seattle", "Seahawks", ()),
    ("TB", "Tampa Bay", "Buccaneers", ("TAM", "Bucs")),
    ("TEN", "Tennessee", "Titans", ()),
    ("WAS", "Washington", "Commanders", ("WSH",)),
)

_NBA: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("ATL", "Atlanta", "Hawks", ()),
    ("BOS", "Boston", "Celtics", ()),
    ("BKN", "Brooklyn", "Nets", ("BRK",)),
    ("CHA", "Charlotte", "Hornets", ("CHO",)),
    ("CHI", "Chicago", "Bulls", ()),
    ("CLE", "Cleveland", "Cavaliers", ("Cavs",)),
    ("DAL", "Dallas", "Mavericks", ("Mavs",)),
    ("DEN", "Denver", "Nuggets", ()),
    ("DET", "Detroit", "Pistons", ()),
    ("GSW", "Golden State", "Warriors", ("GS",)),
    ("HOU", "Houston", "Rockets", ()),
    ("IND", "Indiana", "Pacers", ()),
    ("LAC", "Los Angeles", "Clippers", ("LA Clippers",)),
    ("LAL", "Los Angeles", "Lakers", ("LA Lakers",)),
    ("MEM", "Memphis", "Grizzlies", ()),
    ("MIA", "Miami", "Heat", ()),
    ("MIL", "Milwaukee", "Bucks", ()),
    ("MIN", "Minnesota", "Timberwolves", ("Wolves",)),
    ("NOP", "New Orleans", "Pelicans", ("NO",)),
    ("NYK", "New York", "Knicks", ("NY Knicks", "NY")),
    ("OKC", "Oklahoma City", "Thunder", ()),
    ("ORL", "Orlando", "Magic", ()),
    ("PHI", "Philadelphia", "76ers", ("Sixers", "PHL")),
    ("PHX", "Phoenix", "Suns", ("PHO",)),
    ("POR", "Portland", "Trail Blazers", ("Blazers",)),
    ("SAC", "Sacramento", "Kings", ()),
    ("SAS", "San Antonio", "Spurs", ("SA",)),
    ("TOR", "Toronto", "Raptors", ()),
    ("UTA", "Utah", "Jazz", ("UTAH",)),
    ("WAS", "Washington", "Wizards", ("WSH",)),
)


def _teams(sport: Sport, rows: tuple[tuple[str, str, str, tuple[str, ...]], ...]) -> list[Participant]:
    out = []
    for abbr, city, nickname, extra in rows:
        full = f"{city} {nickname}"
        aliases = frozenset({abbr, city, nickname, full, *extra})
        out.append(
            Participant(
                sport=sport,
                key=f"{sport.value}:{abbr}",
                kind=ParticipantKind.TEAM,
                display_name=full,
                aliases=aliases,
            )
        )
    return out


def seed_participants() -> list[Participant]:
    return [*_teams(Sport.NFL, _NFL), *_teams(Sport.NBA, _NBA)]


def seeded_registry() -> ParticipantRegistry:
    return ParticipantRegistry(seed_participants())
