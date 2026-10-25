"""Source wagers: a wallet's fills aggregated into net position increases (audit rec. 3).

One betting decision on Polymarket is often many fills over seconds or
minutes (a large order walking the book, or a resting order filled piecemeal).
Copying each fill would duplicate signals and correlate the sample, so a
wallet's consecutive BUY fills on one outcome token, each within
``window_seconds`` of the previous one, form a single wager. A SELL on that
token ends the run and is never a wager itself (v1 holds to settlement and
only copies entries).

The copy signal fires when the *first* fill of a wager is detected, so the
wager's ``detected_at`` is that fill's first observation time, not the last.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class SourceFill:
    wallet: str
    market_id: str
    book_key: str  # Outcome token id
    side: str  # BUY / SELL from the wallet's perspective
    price: Decimal
    size: Decimal  # Shares ($1-payout contracts)
    ts: datetime  # Block time
    observed_at: datetime  # When our poll first returned it
    taker: bool | None = None  # Also seen in the taker-only feed


@dataclass(frozen=True)
class Wager:
    wallet: str
    market_id: str
    book_key: str
    price: Decimal  # Size-weighted average fill price
    size: Decimal
    first_ts: datetime
    last_ts: datetime
    detected_at: datetime
    fills: int
    taker_share: Decimal | None  # Share of size from fills seen in the taker feed

    @property
    def notional(self) -> Decimal:
        return self.price * self.size


def aggregate_wagers(fills: Iterable[SourceFill], window_seconds: float) -> list[Wager]:
    by_key: dict[tuple[str, str], list[SourceFill]] = defaultdict(list)
    for f in fills:
        by_key[(f.wallet, f.book_key)].append(f)
    wagers: list[Wager] = []
    for run in by_key.values():
        run.sort(key=lambda f: (f.ts, f.observed_at))
        current: list[SourceFill] = []
        for f in run:
            if f.side != "BUY":
                wagers += _close(current)
                current = []
                continue
            if current and (f.ts - current[-1].ts).total_seconds() > window_seconds:
                wagers += _close(current)
                current = []
            current.append(f)
        wagers += _close(current)
    wagers.sort(key=lambda w: (w.detected_at, w.wallet))
    return wagers


def _close(fills: list[SourceFill]) -> list[Wager]:
    if not fills:
        return []
    size = sum((f.size for f in fills), Decimal(0))
    if size <= 0:
        return []
    known = [f for f in fills if f.taker is not None]
    taker_share = (
        sum((f.size for f in known if f.taker), Decimal(0))
        / sum((f.size for f in known), Decimal(0))
        if known
        else None
    )
    return [
        Wager(
            wallet=fills[0].wallet,
            market_id=fills[0].market_id,
            book_key=fills[0].book_key,
            price=sum((f.price * f.size for f in fills), Decimal(0)) / size,
            size=size,
            first_ts=fills[0].ts,
            last_ts=fills[-1].ts,
            detected_at=min(f.observed_at for f in fills),
            fills=len(fills),
            taker_share=taker_share,
        )
    ]
