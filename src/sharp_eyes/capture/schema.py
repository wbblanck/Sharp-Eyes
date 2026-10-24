"""Phase 0 capture tables (PostgreSQL schema ``capture``).

These tables are deliberately venue-shaped and append-mostly. They record what
each venue said and when we saw it; the canonical Phase 1 model (events,
listings, contract matches) is built from them later and lives elsewhere.

Time columns:
* ``observed_at``: when our response arrived (UTC). The only clock every venue
  shares, and the one a backtest must use to avoid look-ahead.
* ``ts`` / ``venue_ts``: the venue's own timestamp, never overwritten.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

SCHEMA = "capture"

metadata = MetaData(
    schema=SCHEMA,
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "pk": "pk_%(table_name)s",
    },
)

Price = Numeric(12, 6)
Size = Numeric(24, 6)


def _ts(name: str, **kwargs: object) -> Column[object]:
    return Column(name, DateTime(timezone=True), **kwargs)  # type: ignore[arg-type]


events = Table(
    "events",
    metadata,
    Column("venue", String(20), nullable=False),
    Column("event_id", String(200), nullable=False),
    Column("league", String(20), nullable=False),
    Column("title", Text, nullable=False),
    _ts("start_time"),
    Column("status", String(40), nullable=False),
    Column("raw", JSONB, nullable=False),
    Column("content_hash", String(32), nullable=False),
    _ts("first_seen_at", nullable=False, server_default=func.now()),
    _ts("last_seen_at", nullable=False, server_default=func.now()),
    _ts("last_changed_at", nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("venue", "event_id"),
    Index(None, "start_time"),
)

markets = Table(
    "markets",
    metadata,
    Column("venue", String(20), nullable=False),
    Column("market_id", String(200), nullable=False),
    Column("event_id", String(200), nullable=False),
    Column("venue_market_type", String(100), nullable=False),
    Column("bet_type", String(20), nullable=False),
    Column("period", String(20), nullable=False),
    Column("line", Numeric(10, 2)),
    Column("title", Text, nullable=False),
    Column("status", String(40), nullable=False),
    _ts("start_time"),
    Column("books", JSONB, nullable=False),  # [{"book_key": ..., "outcome": ...}]
    Column("raw", JSONB, nullable=False),
    Column("content_hash", String(32), nullable=False),
    _ts("first_seen_at", nullable=False, server_default=func.now()),
    _ts("last_seen_at", nullable=False, server_default=func.now()),
    _ts("last_changed_at", nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("venue", "market_id"),
    Index(None, "venue", "event_id"),
)

# Append-only history: one row each time an event or market's stable content
# (prices and volumes stripped) changes, e.g. a status change or relisting.
catalog_versions = Table(
    "catalog_versions",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("venue", String(20), nullable=False),
    Column("kind", String(10), nullable=False),  # event | market
    Column("object_id", String(200), nullable=False),
    _ts("observed_at", nullable=False),
    Column("content_hash", String(32), nullable=False),
    Column("raw", JSONB, nullable=False),
    Index(None, "venue", "kind", "object_id", "observed_at"),
)

# One row per book whose content changed since the previous stored snapshot of
# that book. A book is unchanged between two rows for as long as poll_runs show
# the venue's book job running without gaps.
book_snapshots = Table(
    "book_snapshots",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("venue", String(20), nullable=False),
    Column("market_id", String(200), nullable=False),
    Column("book_key", String(200), nullable=False),
    _ts("observed_at", nullable=False),
    _ts("venue_ts"),
    Column("seq", BigInteger),
    Column("best_bid", Price),
    Column("best_ask", Price),
    Column("bids", JSONB, nullable=False),  # [[price, size], ...] best first
    Column("asks", JSONB, nullable=False),
    Column("content_hash", String(32), nullable=False),
    Column("extra", JSONB),
    Column("request_ms", Integer),
    Index(None, "venue", "book_key", "observed_at"),
    Index("ix_book_snapshots_observed_at_brin", "observed_at", postgresql_using="brin"),
)

trades = Table(
    "trades",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("venue", String(20), nullable=False),
    Column("trade_key", Text, nullable=False),
    Column("market_id", String(200), nullable=False),
    Column("book_key", String(200), nullable=False),
    _ts("ts", nullable=False),
    _ts("observed_at", nullable=False),  # First time any feed returned it
    _ts("api_observed_at"),  # First time a REST poll returned it
    _ts("ws_observed_at"),  # When the Polymarket websocket pushed it
    _ts("prev_poll_at"),  # Previous REST poll of the same scope that did not return it
    Column("price", Price, nullable=False),
    Column("size", Size, nullable=False),  # $1-payout contracts
    Column("side", String(10)),
    Column("taker_side", String(10)),
    Column("wallet", String(64)),
    Column("tx_hash", String(80)),
    Column("seen_in_taker_feed", Boolean),
    Column("raw", JSONB, nullable=False),
    UniqueConstraint("venue", "trade_key"),
    Index(None, "venue", "ts"),
    Index(None, "venue", "market_id", "ts"),
    Index("ix_trades_wallet_ts", "wallet", "ts", postgresql_where="wallet IS NOT NULL"),
)

poll_runs = Table(
    "poll_runs",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("venue", String(20), nullable=False),
    Column("job", String(30), nullable=False),  # catalog | books | trades | status | backfill
    _ts("started_at", nullable=False),
    _ts("finished_at", nullable=False),
    Column("ok", Boolean, nullable=False),
    Column("requests", Integer, nullable=False, server_default="0"),
    Column("items", Integer, nullable=False, server_default="0"),
    Column("changed", Integer, nullable=False, server_default="0"),
    Column("error", Text),
    Index(None, "venue", "job", "started_at"),
)

checkpoints = Table(
    "checkpoints",
    metadata,
    Column("venue", String(20), nullable=False),
    Column("key", String(250), nullable=False),
    Column("value", Text, nullable=False),
    _ts("updated_at", nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("venue", "key"),
)

# Polymarket Data API /v2/status samples: the API's own indexing lag.
api_status_samples = Table(
    "api_status_samples",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("venue", String(20), nullable=False),
    _ts("observed_at", nullable=False),
    Column("lag_seconds", Numeric(10, 3)),
    Column("raw", JSONB, nullable=False),
    Index(None, "venue", "observed_at"),
)
