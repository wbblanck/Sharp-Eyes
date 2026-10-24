"""Canonical sporting events.

An event is identified by its sport, its participants and its scheduled start,
never by venue wording. Team-sport events are keyed on home and away teams and
the US Eastern calendar date of the scheduled start (NFL and NBA schedule by
Eastern date, and a late game can cross midnight UTC). Tennis matches are keyed
on the unordered player pair, the tournament and the UTC date.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from sharp_eyes.taxonomy.categories import Sport

_EASTERN = ZoneInfo("America/New_York")


class EventStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    FINAL = "FINAL"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    SUSPENDED = "SUSPENDED"
    # Tennis-specific terminal states
    RETIRED = "RETIRED"
    WALKOVER = "WALKOVER"
    ABANDONED = "ABANDONED"


class TennisFormat(StrEnum):
    BEST_OF_3 = "BO3"
    BEST_OF_5 = "BO5"


class CanonicalEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sport: Sport
    scheduled_start: datetime
    # Team sports: home and away. Tennis: player_a/player_b in any order.
    home: str | None = None
    away: str | None = None
    players: tuple[str, str] | None = None
    competition: str | None = None  # Tennis tournament slug; season/week for others
    match_format: TennisFormat | None = None
    surface: str | None = None

    @field_validator("scheduled_start")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("scheduled_start must be timezone-aware")
        return v.astimezone(UTC)

    @model_validator(mode="after")
    def _shape(self) -> CanonicalEvent:
        if self.sport is Sport.TENNIS:
            if self.players is None or self.home or self.away:
                raise ValueError("tennis events name two players, not home/away")
            if self.players[0] == self.players[1]:
                raise ValueError("a player cannot play themselves")
            if self.competition is None or self.match_format is None:
                raise ValueError("tennis events need a competition and match format")
        else:
            if self.home is None or self.away is None or self.players is not None:
                raise ValueError(f"{self.sport} events need home and away teams")
            if self.home == self.away:
                raise ValueError("home and away must differ")
        return self

    def event_key(self) -> str:
        if self.sport is Sport.TENNIS:
            assert self.players is not None
            a, b = sorted(self.players)
            day = self.scheduled_start.date().isoformat()
            return f"TENNIS|{self.competition}|{day}|{a}|{b}"
        day = self.scheduled_start.astimezone(_EASTERN).date().isoformat()
        return f"{self.sport.value}|{day}|{self.away}@{self.home}"

    def participant_keys(self) -> frozenset[str]:
        if self.players is not None:
            return frozenset(self.players)
        assert self.home is not None and self.away is not None
        return frozenset({self.home, self.away})


def same_event(
    a: CanonicalEvent, b: CanonicalEvent, start_tolerance: timedelta = timedelta(hours=3)
) -> bool:
    """Whether two venue descriptions refer to the same real event.

    Participants must agree exactly (and home/away must not be swapped); the
    scheduled starts may differ by up to ``start_tolerance`` because venues
    often list an approximate time. Tennis start times are frequently
    "not before" estimates, so callers may pass a wider tolerance there.
    """
    if a.sport is not b.sport or a.participant_keys() != b.participant_keys():
        return False
    if a.sport is not Sport.TENNIS and (a.home, a.away) != (b.home, b.away):
        return False
    if a.sport is Sport.TENNIS and (a.competition != b.competition):
        return False
    return abs(a.scheduled_start - b.scheduled_start) <= start_tolerance
