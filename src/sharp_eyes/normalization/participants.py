"""Participant identities and explicit aliases (spec 7.1).

Venue text is resolved to a canonical participant only through an explicit
alias table. There is deliberately no fuzzy matching: an unknown or ambiguous
name resolves to nothing, and the caller must reject or queue the record for
review rather than guess.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from sharp_eyes.taxonomy.categories import Sport


class ParticipantKind(StrEnum):
    TEAM = "TEAM"
    PLAYER = "PLAYER"


@dataclass(frozen=True)
class Participant:
    sport: Sport
    key: str  # Canonical key, e.g. "NFL:KC" or "TENNIS:sinner-jannik"
    kind: ParticipantKind
    display_name: str
    aliases: frozenset[str] = field(default_factory=frozenset)


class AliasConflictError(ValueError):
    """Two participants of the same sport claim the same alias."""


_PUNCT = re.compile(r"[^\w\s]")
_SPACE = re.compile(r"\s+")


def normalize_alias(text: str) -> str:
    """Casefold, strip accents and punctuation, and collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    no_punct = _PUNCT.sub(" ", stripped.casefold())
    return _SPACE.sub(" ", no_punct).strip()


class ParticipantRegistry:
    """In-memory alias resolver, loaded from seeds and the ``participant_aliases`` table."""

    def __init__(self, participants: Iterable[Participant] = ()) -> None:
        self._by_key: dict[str, Participant] = {}
        self._aliases: dict[tuple[Sport, str], set[str]] = {}
        for p in participants:
            self.add(p)

    def add(self, participant: Participant) -> None:
        if participant.key in self._by_key:
            raise AliasConflictError(f"duplicate participant key {participant.key}")
        self._by_key[participant.key] = participant
        names = {participant.display_name, *participant.aliases}
        for name in names:
            self.add_alias(participant.sport, name, participant.key)

    def add_alias(self, sport: Sport, alias: str, key: str) -> None:
        if key not in self._by_key:
            raise KeyError(key)
        norm = normalize_alias(alias)
        if not norm:
            raise ValueError("empty alias")
        # Shared aliases are recorded, not rejected: "Los Angeles" really does
        # name two NFL teams. Resolution then reports the ambiguity.
        self._aliases.setdefault((sport, norm), set()).add(key)

    def get(self, key: str) -> Participant:
        return self._by_key[key]

    def candidates(self, sport: Sport, text: str) -> frozenset[str]:
        return frozenset(self._aliases.get((sport, normalize_alias(text)), set()))

    def resolve(self, sport: Sport, text: str) -> str | None:
        """The canonical key for ``text``, or ``None`` if unknown or ambiguous."""
        found = self.candidates(sport, text)
        return next(iter(found)) if len(found) == 1 else None

    def __len__(self) -> int:
        return len(self._by_key)

    def __iter__(self) -> Iterator[Participant]:
        return iter(self._by_key.values())
