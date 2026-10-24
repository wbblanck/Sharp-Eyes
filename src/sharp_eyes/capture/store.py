"""Persistence for the capture worker (synchronous SQLAlchemy Core).

The worker calls these methods through ``asyncio.to_thread``. Every write is
idempotent: re-running a poll can neither duplicate a trade nor create a book
row for an unchanged book.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, case, func, literal_column, select, text
from sqlalchemy.dialects.postgresql import insert

from sharp_eyes.capture import schema as s
from sharp_eyes.capture.records import (
    BookSnapshot,
    EventRecord,
    MarketRecord,
    TradeRecord,
    content_hash,
)
from sharp_eyes.capture.venues.base import Catalog

BATCH = 2000


def _levels(levels: Sequence[tuple[Decimal, Decimal]]) -> list[list[str]]:
    return [[str(p), str(q)] for p, q in levels]


class CaptureStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    # -- catalog ---------------------------------------------------------

    def upsert_catalog(
        self, venue: str, catalog: Catalog, stable_view: Callable[[Any], Any], observed_at: datetime
    ) -> int:
        """Upsert events and markets; append a version row for each change.

        Returns how many objects were new or changed.
        """
        changed = 0
        changed += self._upsert(
            s.events,
            "event",
            "event_id",
            venue,
            [(e.event_id, _event_row(e), stable_view(e.raw)) for e in catalog.events],
            observed_at,
        )
        changed += self._upsert(
            s.markets,
            "market",
            "market_id",
            venue,
            [(m.market_id, _market_row(m), stable_view(m.raw)) for m in catalog.markets],
            observed_at,
        )
        return changed

    def _upsert(
        self,
        table: Any,
        kind: str,
        id_col: str,
        venue: str,
        rows: list[tuple[str, dict[str, Any], Any]],
        observed_at: datetime,
    ) -> int:
        if not rows:
            return 0
        rows = list({oid: (oid, row, stable) for oid, row, stable in rows}.values())
        changed = 0
        with self.engine.begin() as conn:
            for start in range(0, len(rows), BATCH):
                part = rows[start : start + BATCH]
                ids = [oid for oid, _, _ in part]
                existing: dict[str, str] = {
                    oid: h
                    for oid, h in conn.execute(
                        select(table.c[id_col], table.c.content_hash).where(
                            table.c.venue == venue, table.c[id_col].in_(ids)
                        )
                    )
                }
                values, versions = [], []
                for oid, row, stable in part:
                    h = content_hash(stable)
                    values.append(
                        {
                            **row,
                            "venue": venue,
                            id_col: oid,
                            "content_hash": h,
                            "last_seen_at": observed_at,
                        }
                    )
                    if existing.get(oid) != h:
                        versions.append(
                            {
                                "venue": venue,
                                "kind": kind,
                                "object_id": oid,
                                "observed_at": observed_at,
                                "content_hash": h,
                                "raw": row["raw"],
                            }
                        )
                stmt = insert(table).values(values)
                update: dict[str, Any] = {
                    c: stmt.excluded[c] for c in values[0] if c not in ("venue", id_col)
                }
                update["last_changed_at"] = case(
                    (
                        stmt.excluded.content_hash != table.c.content_hash,
                        stmt.excluded.last_seen_at,
                    ),
                    else_=table.c.last_changed_at,
                )
                conn.execute(
                    stmt.on_conflict_do_update(index_elements=["venue", id_col], set_=update)
                )
                if versions:
                    conn.execute(s.catalog_versions.insert(), versions)
                changed += len(versions)
        return changed

    def load_markets(self, venue: str, since: datetime) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(s.markets).where(s.markets.c.venue == venue, s.markets.c.start_time >= since)
            ).mappings()
            return [dict(r) for r in rows]

    # -- books -----------------------------------------------------------

    def latest_book_hashes(self, venue: str) -> dict[str, str]:
        sql = text(
            f"SELECT DISTINCT ON (book_key) book_key, content_hash FROM {s.SCHEMA}.book_snapshots "
            "WHERE venue = :venue ORDER BY book_key, observed_at DESC"
        )
        with self.engine.connect() as conn:
            return {k: h for k, h in conn.execute(sql, {"venue": venue}).all()}

    def insert_books(self, snaps: Sequence[BookSnapshot]) -> None:
        rows = [
            {
                "venue": b.venue.value,
                "market_id": b.market_id,
                "book_key": b.book_key,
                "observed_at": b.observed_at,
                "venue_ts": b.venue_ts,
                "seq": b.seq,
                "best_bid": b.best_bid,
                "best_ask": b.best_ask,
                "bids": _levels(b.bids),
                "asks": _levels(b.asks),
                "content_hash": b.content_hash(),
                "extra": b.extra,
                "request_ms": b.request_ms,
            }
            for b in snaps
        ]
        if not rows:
            return
        with self.engine.begin() as conn:
            for start in range(0, len(rows), BATCH):
                conn.execute(s.book_snapshots.insert(), rows[start : start + BATCH])

    # -- trades ----------------------------------------------------------

    def insert_trades(self, trades: Sequence[TradeRecord]) -> int:
        """Insert new trades and merge sightings of known ones.

        A fill seen again keeps its first ``observed_at`` overall and gains the
        first sighting of the other feed (REST poll or websocket), plus the
        taker mark. Returns the number of new trades.
        """
        if not trades:
            return 0
        rows = list(
            {
                t.trade_key: {
                    "venue": t.venue.value,
                    "trade_key": t.trade_key,
                    "market_id": t.market_id,
                    "book_key": t.book_key,
                    "ts": t.ts,
                    "observed_at": t.observed_at or t.ts,
                    "api_observed_at": (t.observed_at or t.ts) if t.source == "api" else None,
                    "ws_observed_at": (t.observed_at or t.ts) if t.source == "ws" else None,
                    "prev_poll_at": t.prev_poll_at,
                    "price": t.price,
                    "size": t.size,
                    "side": t.side,
                    "taker_side": t.taker_side,
                    "wallet": t.wallet,
                    "tx_hash": t.tx_hash,
                    "seen_in_taker_feed": t.seen_in_taker_feed,
                    "raw": t.raw,
                }
                for t in trades
            }.values()
        )
        new = 0
        with self.engine.begin() as conn:
            for start in range(0, len(rows), BATCH):
                ins = insert(s.trades).values(rows[start : start + BATCH])
                old, new_ = s.trades.c, ins.excluded
                stmt: Any = ins.on_conflict_do_update(
                    index_elements=["venue", "trade_key"],
                    set_={
                        "observed_at": func.least(old.observed_at, new_.observed_at),
                        "api_observed_at": func.coalesce(old.api_observed_at, new_.api_observed_at),
                        "ws_observed_at": func.coalesce(old.ws_observed_at, new_.ws_observed_at),
                        # Latency bounds belong to the first REST poll that returned it.
                        "prev_poll_at": case(
                            (old.api_observed_at.is_(None), new_.prev_poll_at),
                            else_=old.prev_poll_at,
                        ),
                        "seen_in_taker_feed": case(
                            (new_.seen_in_taker_feed.is_(True), True),
                            else_=func.coalesce(old.seen_in_taker_feed, new_.seen_in_taker_feed),
                        ),
                    },
                    # Only touch rows that gain something, so the 10-minute
                    # re-read every 2 s does not rewrite every recent fill.
                    where=(
                        new_.seen_in_taker_feed.is_(True)
                        & old.seen_in_taker_feed.is_distinct_from(True)
                    )
                    | (old.seen_in_taker_feed.is_(None) & new_.seen_in_taker_feed.isnot(None))
                    | (old.api_observed_at.is_(None) & new_.api_observed_at.isnot(None))
                    | (old.ws_observed_at.is_(None) & new_.ws_observed_at.isnot(None)),
                ).returning(literal_column("(xmax = 0)").label("inserted"))
                new += sum(1 for (inserted,) in conn.execute(stmt).all() if inserted)
        return new

    # -- checkpoints, runs, status ---------------------------------------

    def get_checkpoints(self, venue: str) -> dict[str, str]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(s.checkpoints.c.key, s.checkpoints.c.value).where(
                    s.checkpoints.c.venue == venue
                )
            ).all()
            return {k: v for k, v in rows}

    def set_checkpoints(self, venue: str, values: dict[str, str]) -> None:
        if not values:
            return
        rows = [{"venue": venue, "key": k, "value": v} for k, v in values.items()]
        stmt = insert(s.checkpoints).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["venue", "key"],
            set_={"value": stmt.excluded.value, "updated_at": func.now()},
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def record_poll(
        self,
        venue: str,
        job: str,
        started_at: datetime,
        finished_at: datetime,
        *,
        ok: bool,
        requests: int = 0,
        items: int = 0,
        changed: int = 0,
        error: str | None = None,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                s.poll_runs.insert().values(
                    venue=venue,
                    job=job,
                    started_at=started_at,
                    finished_at=finished_at,
                    ok=ok,
                    requests=requests,
                    items=items,
                    changed=changed,
                    error=error[:2000] if error else None,
                )
            )

    def add_status_sample(
        self, venue: str, observed_at: datetime, lag: Decimal | None, raw: dict[str, Any]
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                s.api_status_samples.insert().values(
                    venue=venue, observed_at=observed_at, lag_seconds=lag, raw=raw
                )
            )


def _event_row(e: EventRecord) -> dict[str, Any]:
    return {
        "league": e.league,
        "title": e.title,
        "start_time": e.start_time,
        "status": e.status,
        "raw": e.raw,
    }


def _market_row(m: MarketRecord) -> dict[str, Any]:
    return {
        "event_id": m.event_id,
        "venue_market_type": m.venue_market_type,
        "bet_type": m.bet_type.value,
        "period": m.period.value,
        "line": m.line,
        "title": m.title,
        "status": m.status,
        "start_time": m.start_time,
        "books": [{"book_key": b.book_key, "outcome": b.outcome} for b in m.books],
        "raw": m.raw,
    }
