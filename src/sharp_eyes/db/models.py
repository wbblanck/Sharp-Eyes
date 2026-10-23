"""Canonical PostgreSQL schema (spec section 12).

Conventions:
* UUID primary keys; source-native identifiers are kept in their own columns.
* All timestamps are timezone-aware UTC.
* Prices, money and quantities are exact ``NUMERIC``.
* Unique constraints carry the idempotency guarantees: a repeated API response,
  retried job or second worker cannot create a second trade, signal, order,
  fill, ledger entry or settlement.
* ``audit_events`` and ``trader_qualification_history`` are append-only; the
  migration installs triggers that reject UPDATE and DELETE on them.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from sharp_eyes.db.base import Base, CreatedAt, JsonB, Price, Quantity, UUIDPk, enum_column, utcnow
from sharp_eyes.domain import (
    ActivityClass,
    BookSide,
    IngestionStatus,
    LedgerEntryType,
    ListingStatus,
    MatchState,
    PaperOrderState,
    PositionStatus,
    QualificationStatus,
    SettlementResult,
    Severity,
    SignalState,
    TradeSide,
    Venue,
)
from sharp_eyes.config import PaperExecutionMode
from sharp_eyes.normalization.events import EventStatus
from sharp_eyes.normalization.participants import ParticipantKind
from sharp_eyes.taxonomy.categories import MarketCategory, Period, Sport


def _fk(target: str, *, nullable: bool = False, index: bool = True) -> Mapped[Any]:
    return mapped_column(ForeignKey(target, ondelete="RESTRICT"), nullable=nullable, index=index)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


class IngestionRun(UUIDPk, Base):
    __tablename__ = "ingestion_runs"

    source: Mapped[Venue] = enum_column(Venue)
    job: Mapped[str] = mapped_column(String(100))
    status: Mapped[IngestionStatus] = enum_column(IngestionStatus)
    started_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    finished_at: Mapped[datetime | None]
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    records_seen: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    records_new: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # True only when pagination ran to the documented end (e.g. next_cursor null).
    pagination_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    error: Mapped[str | None] = mapped_column(Text)


class IngestionCheckpoint(UUIDPk, Base):
    __tablename__ = "ingestion_checkpoints"
    __table_args__ = (UniqueConstraint("source", "stream", "scope_key"),)

    source: Mapped[Venue] = enum_column(Venue)
    stream: Mapped[str] = mapped_column(String(100))  # e.g. "v2/trades"
    scope_key: Mapped[str] = mapped_column(String(200))  # e.g. a wallet, or "global"
    cursor: Mapped[str | None] = mapped_column(Text)
    last_source_ts: Mapped[datetime | None]
    last_run_id: Mapped[uuid.UUID | None] = _fk("ingestion_runs.id", nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class RawApiResponse(UUIDPk, Base):
    __tablename__ = "raw_api_responses"
    __table_args__ = (Index("ix_raw_api_responses_source_received", "source", "received_at"),)

    ingestion_run_id: Mapped[uuid.UUID | None] = _fk("ingestion_runs.id", nullable=True)
    source: Mapped[Venue] = enum_column(Venue)
    method: Mapped[str] = mapped_column(String(10), default="GET")
    endpoint: Mapped[str] = mapped_column(String(500))
    request_params: Mapped[dict[str, Any] | None] = mapped_column(JsonB)
    http_status: Mapped[int] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    body: Mapped[dict[str, Any] | None] = mapped_column(JsonB)
    body_sha256: Mapped[str] = mapped_column(String(64), index=True)


class SourceEvent(UUIDPk, Base):
    """One deduplicated record from a source feed (a trade, an activity row...)."""

    __tablename__ = "source_events"
    __table_args__ = (UniqueConstraint("source", "source_event_key"),)

    source: Mapped[Venue] = enum_column(Venue)
    # Stable identity: a native id where the source has one, otherwise a
    # documented composite key (see docs/venue-api-research.md).
    source_event_key: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(50))
    first_raw_response_id: Mapped[uuid.UUID] = _fk("raw_api_responses.id")
    source_ts: Mapped[datetime | None]  # As reported by the source; never replaced
    first_observed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    times_observed: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    payload: Mapped[dict[str, Any]] = mapped_column(JsonB)


class DataQualityIssue(UUIDPk, Base):
    __tablename__ = "data_quality_issues"

    source: Mapped[Venue | None] = enum_column(Venue, nullable=True)
    severity: Mapped[Severity] = enum_column(Severity)
    code: Mapped[str] = mapped_column(String(100), index=True)
    detail: Mapped[str] = mapped_column(Text)
    related_table: Mapped[str | None] = mapped_column(String(100))
    related_id: Mapped[uuid.UUID | None]
    detected_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    resolved_at: Mapped[datetime | None]


# ---------------------------------------------------------------------------
# Sports and markets
# ---------------------------------------------------------------------------


class Participant(UUIDPk, CreatedAt, Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("canonical_key"),)

    sport: Mapped[Sport] = enum_column(Sport)
    canonical_key: Mapped[str] = mapped_column(String(200))
    kind: Mapped[ParticipantKind] = enum_column(ParticipantKind)
    display_name: Mapped[str] = mapped_column(String(200))


class ParticipantAlias(UUIDPk, CreatedAt, Base):
    """Explicit alias table. A shared alias (e.g. "Los Angeles") has several rows."""

    __tablename__ = "participant_aliases"
    __table_args__ = (UniqueConstraint("sport", "normalized_alias", "participant_id"),)

    sport: Mapped[Sport] = enum_column(Sport)
    participant_id: Mapped[uuid.UUID] = _fk("participants.id")
    alias: Mapped[str] = mapped_column(String(200))
    normalized_alias: Mapped[str] = mapped_column(String(200), index=True)
    venue: Mapped[Venue | None] = enum_column(Venue, nullable=True)  # None = any venue
    added_by: Mapped[str] = mapped_column(String(100), default="seed")


class SportEvent(UUIDPk, CreatedAt, Base):
    __tablename__ = "sport_events"
    __table_args__ = (UniqueConstraint("event_key"),)

    sport: Mapped[Sport] = enum_column(Sport)
    event_key: Mapped[str] = mapped_column(String(300))
    competition: Mapped[str | None] = mapped_column(String(200))
    scheduled_start: Mapped[datetime] = mapped_column(index=True)
    status: Mapped[EventStatus] = enum_column(EventStatus)
    match_format: Mapped[str | None] = mapped_column(String(10))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class EventParticipant(UUIDPk, Base):
    __tablename__ = "event_participants"
    __table_args__ = (
        UniqueConstraint("sport_event_id", "participant_id"),
        UniqueConstraint("sport_event_id", "role"),
    )

    sport_event_id: Mapped[uuid.UUID] = _fk("sport_events.id")
    participant_id: Mapped[uuid.UUID] = _fk("participants.id")
    role: Mapped[str] = mapped_column(String(20))  # HOME, AWAY, PLAYER_A, PLAYER_B


class SportEventDetail(UUIDPk, Base):
    """Timestamped event facts: weather, surface, round, inactives, lineups."""

    __tablename__ = "sport_event_details"

    sport_event_id: Mapped[uuid.UUID] = _fk("sport_events.id")
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[dict[str, Any]] = mapped_column(JsonB)
    source: Mapped[Venue] = enum_column(Venue)
    observed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class MarketSettlementRules(UUIDPk, CreatedAt, Base):
    __tablename__ = "market_settlement_rules"
    __table_args__ = (UniqueConstraint("rules_hash"),)

    rules_hash: Mapped[str] = mapped_column(String(64))
    rules: Mapped[dict[str, Any]] = mapped_column(JsonB)


class MarketDefinition(UUIDPk, CreatedAt, Base):
    """A canonical market (see ``sharp_eyes.taxonomy.identity.MarketIdentity``)."""

    __tablename__ = "market_definitions"
    __table_args__ = (UniqueConstraint("identity_key"),)

    identity_key: Mapped[str] = mapped_column(String(64))
    sport_event_id: Mapped[uuid.UUID] = _fk("sport_events.id")
    sport: Mapped[Sport] = enum_column(Sport)
    category: Mapped[MarketCategory] = enum_column(MarketCategory)
    period: Mapped[Period] = enum_column(Period)
    selection: Mapped[str] = mapped_column(String(200))
    line: Mapped[Decimal | None] = mapped_column(Price)
    subject_participant_id: Mapped[uuid.UUID | None] = _fk("participants.id", nullable=True)
    set_number: Mapped[int | None] = mapped_column(Integer)
    prop_stat: Mapped[str | None] = mapped_column(String(100))
    match_format: Mapped[str | None] = mapped_column(String(10))
    settlement_rules_id: Mapped[uuid.UUID] = _fk("market_settlement_rules.id")
    taxonomy_version: Mapped[str] = mapped_column(String(20))


class MarketListing(UUIDPk, Base):
    """A venue's market, as listed. Linked to a canonical definition once classified."""

    __tablename__ = "market_listings"
    __table_args__ = (UniqueConstraint("venue", "venue_market_id"),)

    venue: Mapped[Venue] = enum_column(Venue)
    venue_market_id: Mapped[str] = mapped_column(String(200))  # condition id, ticker, uuid
    venue_event_id: Mapped[str | None] = mapped_column(String(200), index=True)
    market_definition_id: Mapped[uuid.UUID | None] = _fk("market_definitions.id", nullable=True)
    sport_event_id: Mapped[uuid.UUID | None] = _fk("sport_events.id", nullable=True)
    title: Mapped[str] = mapped_column(Text)
    rules_text: Mapped[str | None] = mapped_column(Text)
    settlement_rules_id: Mapped[uuid.UUID | None] = _fk(
        "market_settlement_rules.id", nullable=True
    )
    status: Mapped[ListingStatus] = enum_column(ListingStatus)
    classification_taxonomy_version: Mapped[str | None] = mapped_column(String(20))
    classification_note: Mapped[str | None] = mapped_column(Text)  # why rejected/uncertain
    tick_size: Mapped[Decimal | None] = mapped_column(Price)
    min_order_size: Mapped[Decimal | None] = mapped_column(Quantity)
    fee_model: Mapped[dict[str, Any] | None] = mapped_column(JsonB)
    opens_at: Mapped[datetime | None]
    closes_at: Mapped[datetime | None]
    first_seen_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class MarketOutcome(UUIDPk, Base):
    __tablename__ = "market_outcomes"
    __table_args__ = (UniqueConstraint("market_listing_id", "venue_outcome_id"),)

    market_listing_id: Mapped[uuid.UUID] = _fk("market_listings.id")
    venue_outcome_id: Mapped[str] = mapped_column(String(200))  # token id, "yes"/"no", uuid
    label: Mapped[str] = mapped_column(String(200))
    # The canonical market this outcome *wins* on, when known. For a binary YES/NO
    # listing the YES outcome maps to the definition; NO maps to its complement.
    market_definition_id: Mapped[uuid.UUID | None] = _fk("market_definitions.id", nullable=True)


# ---------------------------------------------------------------------------
# Trader research
# ---------------------------------------------------------------------------


class Trader(UUIDPk, CreatedAt, Base):
    __tablename__ = "traders"

    display_name: Mapped[str | None] = mapped_column(String(200))
    identity_confidence: Mapped[Decimal | None] = mapped_column(Price)
    notes: Mapped[str | None] = mapped_column(Text)


class TraderSourceAccount(UUIDPk, Base):
    __tablename__ = "trader_source_accounts"
    __table_args__ = (UniqueConstraint("source", "account_ref"),)

    trader_id: Mapped[uuid.UUID] = _fk("traders.id")
    source: Mapped[Venue] = enum_column(Venue)
    account_ref: Mapped[str] = mapped_column(String(200))  # Polymarket proxy wallet (lowercase)
    pseudonym: Mapped[str | None] = mapped_column(String(200))
    discovery_reason: Mapped[str] = mapped_column(String(200))  # e.g. "leaderboard:sports:30d"
    discovered_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    history_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    history_checked_at: Mapped[datetime | None]
    history_start_ts: Mapped[datetime | None]
    last_active_at: Mapped[datetime | None]
    last_evaluated_at: Mapped[datetime | None]


class TraderTrade(UUIDPk, Base):
    __tablename__ = "trader_trades"
    __table_args__ = (
        UniqueConstraint("source_event_id"),
        Index("ix_trader_trades_account_ts", "trader_source_account_id", "source_ts"),
        CheckConstraint("price >= 0 AND price <= 1", name="price_range"),
        CheckConstraint("size > 0", name="size_positive"),
    )

    trader_source_account_id: Mapped[uuid.UUID] = _fk("trader_source_accounts.id")
    source_event_id: Mapped[uuid.UUID] = _fk("source_events.id", index=False)
    market_outcome_id: Mapped[uuid.UUID | None] = _fk("market_outcomes.id", nullable=True)
    activity_class: Mapped[ActivityClass] = enum_column(ActivityClass)
    side: Mapped[TradeSide] = enum_column(TradeSide)
    size: Mapped[Decimal] = mapped_column(Quantity)  # shares
    price: Mapped[Decimal] = mapped_column(Price)
    usdc_size: Mapped[Decimal | None]
    transaction_hash: Mapped[str | None] = mapped_column(String(100))
    source_ts: Mapped[datetime]  # Block timestamp of the fill (Polymarket)
    first_observed_at: Mapped[datetime]


class TraderPosition(UUIDPk, Base):
    """Position snapshots as reported by the source, for reconciliation."""

    __tablename__ = "trader_positions"
    __table_args__ = (UniqueConstraint("trader_source_account_id", "market_outcome_id", "observed_at"),)

    trader_source_account_id: Mapped[uuid.UUID] = _fk("trader_source_accounts.id")
    market_outcome_id: Mapped[uuid.UUID] = _fk("market_outcomes.id")
    status: Mapped[str] = mapped_column(String(30))  # source status, e.g. OPEN/CLOSED/REDEEMABLE
    size: Mapped[Decimal] = mapped_column(Quantity)
    avg_price: Mapped[Decimal | None] = mapped_column(Price)
    entry_cost_usd: Mapped[Decimal | None]
    realized_pnl_usd: Mapped[Decimal | None]
    observed_at: Mapped[datetime]
    raw_response_id: Mapped[uuid.UUID | None] = _fk("raw_api_responses.id", nullable=True)


class TraderLedgerEvent(UUIDPk, Base):
    """Non-trade account activity: redeem, merge, split, conversion, reward..."""

    __tablename__ = "trader_ledger_events"
    __table_args__ = (UniqueConstraint("source_event_id"),)

    trader_source_account_id: Mapped[uuid.UUID] = _fk("trader_source_accounts.id")
    source_event_id: Mapped[uuid.UUID] = _fk("source_events.id", index=False)
    market_outcome_id: Mapped[uuid.UUID | None] = _fk("market_outcomes.id", nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    activity_class: Mapped[ActivityClass] = enum_column(ActivityClass)
    size: Mapped[Decimal | None] = mapped_column(Quantity)
    amount_usd: Mapped[Decimal | None]
    source_ts: Mapped[datetime]


class TraderMetric(UUIDPk, CreatedAt, Base):
    __tablename__ = "trader_metrics"
    __table_args__ = (
        Index("ix_trader_metrics_key", "trader_id", "sport", "market_category", "as_of"),
    )

    trader_id: Mapped[uuid.UUID] = _fk("traders.id")
    sport: Mapped[Sport] = enum_column(Sport)
    market_category: Mapped[MarketCategory] = enum_column(MarketCategory)
    market_subcategory: Mapped[str] = mapped_column(String(100), default="", server_default="")
    # Only information available strictly before as_of was used (spec 13.1).
    as_of: Mapped[datetime]
    window: Mapped[str] = mapped_column(String(40))  # e.g. "all", "180d"
    model_version: Mapped[str] = mapped_column(String(40))
    taxonomy_version: Mapped[str] = mapped_column(String(20))
    n_observed: Mapped[int] = mapped_column(Integer)
    n_settled: Mapped[int] = mapped_column(Integer)
    n_events: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict[str, Any]] = mapped_column(JsonB)


class TraderQualification(UUIDPk, Base):
    """Current qualification per trader x sport x category x subcategory."""

    __tablename__ = "trader_qualifications"
    __table_args__ = (
        UniqueConstraint("trader_id", "sport", "market_category", "market_subcategory"),
    )

    trader_id: Mapped[uuid.UUID] = _fk("traders.id")
    sport: Mapped[Sport] = enum_column(Sport)
    market_category: Mapped[MarketCategory] = enum_column(MarketCategory)
    market_subcategory: Mapped[str] = mapped_column(String(100), default="", server_default="")
    qualification_period: Mapped[str] = mapped_column(String(40))
    model_version: Mapped[str] = mapped_column(String(40))
    taxonomy_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[QualificationStatus] = enum_column(QualificationStatus)
    trader_metric_id: Mapped[uuid.UUID | None] = _fk("trader_metrics.id", nullable=True)
    effective_at: Mapped[datetime]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class TraderQualificationHistory(UUIDPk, Base):
    """Append-only record of every qualification decision (spec 5.6)."""

    __tablename__ = "trader_qualification_history"
    __table_args__ = (Index("ix_tqh_qualification_effective", "trader_qualification_id", "effective_at"),)

    trader_qualification_id: Mapped[uuid.UUID] = _fk("trader_qualifications.id", index=False)
    previous_status: Mapped[QualificationStatus | None] = enum_column(
        QualificationStatus, nullable=True
    )
    new_status: Mapped[QualificationStatus] = enum_column(QualificationStatus)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JsonB)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JsonB)
    model_version: Mapped[str] = mapped_column(String(40))
    taxonomy_version: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    effective_at: Mapped[datetime]
    decided_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


class Quote(UUIDPk, Base):
    __tablename__ = "quotes"
    __table_args__ = (Index("ix_quotes_outcome_received", "market_outcome_id", "received_at"),)

    market_outcome_id: Mapped[uuid.UUID] = _fk("market_outcomes.id", index=False)
    venue: Mapped[Venue] = enum_column(Venue)
    best_bid: Mapped[Decimal | None] = mapped_column(Price)
    best_bid_size: Mapped[Decimal | None] = mapped_column(Quantity)
    best_ask: Mapped[Decimal | None] = mapped_column(Price)
    best_ask_size: Mapped[Decimal | None] = mapped_column(Quantity)
    quote_ts: Mapped[datetime | None]  # Venue timestamp, when the venue supplies one
    received_at: Mapped[datetime]
    market_status: Mapped[ListingStatus] = enum_column(ListingStatus)
    is_executable: Mapped[bool] = mapped_column(Boolean)  # False = indicative/derived
    source_method: Mapped[str] = mapped_column(String(100))  # e.g. "clob:/book"
    fee_estimate: Mapped[dict[str, Any] | None] = mapped_column(JsonB)
    orderbook_snapshot_id: Mapped[uuid.UUID | None] = _fk("orderbook_snapshots.id", nullable=True)


class OrderbookSnapshot(UUIDPk, Base):
    __tablename__ = "orderbook_snapshots"
    __table_args__ = (Index("ix_orderbook_snapshots_listing_received", "market_listing_id", "received_at"),)

    market_listing_id: Mapped[uuid.UUID] = _fk("market_listings.id", index=False)
    venue: Mapped[Venue] = enum_column(Venue)
    venue_seq: Mapped[int | None] = mapped_column(BigInteger)
    venue_hash: Mapped[str | None] = mapped_column(String(200))
    venue_ts: Mapped[datetime | None]
    received_at: Mapped[datetime]
    # False when the venue truncated depth (e.g. Novig REST returns at most 20 levels).
    depth_complete: Mapped[bool] = mapped_column(Boolean)
    max_levels_requested: Mapped[int | None] = mapped_column(Integer)
    raw_response_id: Mapped[uuid.UUID | None] = _fk("raw_api_responses.id", nullable=True)


class OrderbookLevel(Base):
    __tablename__ = "orderbook_levels"

    orderbook_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orderbook_snapshots.id", ondelete="CASCADE"), primary_key=True
    )
    market_outcome_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("market_outcomes.id", ondelete="RESTRICT"), primary_key=True
    )
    side: Mapped[BookSide] = enum_column(BookSide, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, primary_key=True)  # 0 = best
    price: Mapped[Decimal] = mapped_column(Price)
    size: Mapped[Decimal] = mapped_column(Quantity)
    # Kalshi publishes bids only; asks are derived as 1 - opposite bid.
    derived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class MarketPriceHistory(UUIDPk, Base):
    __tablename__ = "market_price_history"
    __table_args__ = (UniqueConstraint("market_outcome_id", "source_method", "resolution_seconds", "ts"),)

    market_outcome_id: Mapped[uuid.UUID] = _fk("market_outcomes.id", index=False)
    ts: Mapped[datetime]
    price: Mapped[Decimal] = mapped_column(Price)
    source_method: Mapped[str] = mapped_column(String(100))
    resolution_seconds: Mapped[int] = mapped_column(Integer)
    # Price history is never executable liquidity.
    is_executable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class ContractMatchCandidate(UUIDPk, Base):
    __tablename__ = "contract_match_candidates"
    __table_args__ = (
        UniqueConstraint("source_listing_id", "target_listing_id", "matcher_version"),
    )

    source_listing_id: Mapped[uuid.UUID] = _fk("market_listings.id")
    target_listing_id: Mapped[uuid.UUID] = _fk("market_listings.id")
    state: Mapped[MatchState] = enum_column(MatchState)
    differences: Mapped[dict[str, Any]] = mapped_column(JsonB)
    matcher_version: Mapped[str] = mapped_column(String(40))
    evaluated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class ContractMatch(UUIDPk, Base):
    __tablename__ = "contract_matches"
    __table_args__ = (
        UniqueConstraint("source_outcome_id", "target_outcome_id", "matcher_version"),
    )

    candidate_id: Mapped[uuid.UUID] = _fk("contract_match_candidates.id")
    # Outcome-level: the target outcome that pays exactly when the source outcome pays.
    source_outcome_id: Mapped[uuid.UUID] = _fk("market_outcomes.id")
    target_outcome_id: Mapped[uuid.UUID] = _fk("market_outcomes.id")
    state: Mapped[MatchState] = enum_column(MatchState)
    matcher_version: Mapped[str] = mapped_column(String(40))
    decided_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    reviewed_by: Mapped[str | None] = mapped_column(String(100))


# ---------------------------------------------------------------------------
# Signals and execution
# ---------------------------------------------------------------------------


class CopySignal(UUIDPk, Base):
    __tablename__ = "copy_signals"
    # One signal per source trade, whichever feed it arrived from first.
    __table_args__ = (UniqueConstraint("trader_trade_id"),)

    trader_trade_id: Mapped[uuid.UUID] = _fk("trader_trades.id", index=False)
    state: Mapped[SignalState] = enum_column(SignalState)
    qualification_history_id: Mapped[uuid.UUID | None] = _fk(
        "trader_qualification_history.id", nullable=True
    )
    qualification_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonB)
    rejection_code: Mapped[str | None] = mapped_column(String(60), index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    # Spec 6.3: every timestamp persisted separately.
    source_trade_ts: Mapped[datetime]
    source_indexed_ts: Mapped[datetime | None]
    first_observed_at: Mapped[datetime]
    normalized_at: Mapped[datetime | None]
    qualification_checked_at: Mapped[datetime | None]
    prices_retrieved_at: Mapped[datetime | None]
    decided_at: Mapped[datetime | None]
    paper_order_simulated_at: Mapped[datetime | None]


class SignalQuote(Base):
    __tablename__ = "signal_quotes"

    copy_signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("copy_signals.id", ondelete="RESTRICT"), primary_key=True
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quotes.id", ondelete="RESTRICT"), primary_key=True
    )


class SignalEvaluation(UUIDPk, Base):
    """One candidate venue for a signal, with its price and EV inputs."""

    __tablename__ = "signal_evaluations"
    __table_args__ = (UniqueConstraint("copy_signal_id", "target_outcome_id"),)

    copy_signal_id: Mapped[uuid.UUID] = _fk("copy_signals.id")
    target_outcome_id: Mapped[uuid.UUID] = _fk("market_outcomes.id")
    venue: Mapped[Venue] = enum_column(Venue)
    match_state: Mapped[MatchState] = enum_column(MatchState)
    quote_id: Mapped[uuid.UUID | None] = _fk("quotes.id", nullable=True)
    orderbook_snapshot_id: Mapped[uuid.UUID | None] = _fk("orderbook_snapshots.id", nullable=True)
    est_fill_price: Mapped[Decimal | None] = mapped_column(Price)
    est_fill_qty: Mapped[Decimal | None] = mapped_column(Quantity)
    est_fee_usd: Mapped[Decimal | None]
    p_market: Mapped[Decimal | None] = mapped_column(Price)
    p_trader: Mapped[Decimal | None] = mapped_column(Price)
    p_model: Mapped[Decimal | None] = mapped_column(Price)
    p_conservative: Mapped[Decimal | None] = mapped_column(Price)
    net_ev_per_contract: Mapped[Decimal | None] = mapped_column(Price)
    eligible: Mapped[bool] = mapped_column(Boolean)
    rank: Mapped[int | None] = mapped_column(Integer)
    ineligible_code: Mapped[str | None] = mapped_column(String(60))
    ineligible_reason: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime]


class RiskDecision(UUIDPk, Base):
    __tablename__ = "risk_decisions"
    __table_args__ = (UniqueConstraint("copy_signal_id"),)

    copy_signal_id: Mapped[uuid.UUID] = _fk("copy_signals.id", index=False)
    signal_evaluation_id: Mapped[uuid.UUID | None] = _fk("signal_evaluations.id", nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean)
    code: Mapped[str] = mapped_column(String(60))
    reason: Mapped[str] = mapped_column(Text)
    exposure_snapshot: Mapped[dict[str, Any]] = mapped_column(JsonB)
    limits_applied: Mapped[dict[str, Any]] = mapped_column(JsonB)
    decided_at: Mapped[datetime]


class PaperOrder(UUIDPk, CreatedAt, Base):
    __tablename__ = "paper_orders"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        UniqueConstraint("copy_signal_id", "execution_mode"),
        CheckConstraint("stake_usd > 0", name="stake_positive"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(200))
    copy_signal_id: Mapped[uuid.UUID] = _fk("copy_signals.id", index=False)
    signal_evaluation_id: Mapped[uuid.UUID] = _fk("signal_evaluations.id")
    risk_decision_id: Mapped[uuid.UUID] = _fk("risk_decisions.id")
    venue: Mapped[Venue] = enum_column(Venue)
    market_outcome_id: Mapped[uuid.UUID] = _fk("market_outcomes.id")
    execution_mode: Mapped[PaperExecutionMode] = enum_column(PaperExecutionMode)
    state: Mapped[PaperOrderState] = enum_column(PaperOrderState)
    stake_usd: Mapped[Decimal]
    limit_price: Mapped[Decimal | None] = mapped_column(Price)
    selected_price: Mapped[Decimal] = mapped_column(Price)
    expected_value_per_contract: Mapped[Decimal] = mapped_column(Price)
    expires_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class PaperFill(UUIDPk, Base):
    __tablename__ = "paper_fills"
    __table_args__ = (
        UniqueConstraint("paper_order_id", "fill_seq"),
        CheckConstraint("qty > 0", name="qty_positive"),
        CheckConstraint("price >= 0 AND price <= 1", name="price_range"),
    )

    paper_order_id: Mapped[uuid.UUID] = _fk("paper_orders.id", index=False)
    fill_seq: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Price)
    qty: Mapped[Decimal] = mapped_column(Quantity)
    fee_usd: Mapped[Decimal]
    slippage_per_contract: Mapped[Decimal | None] = mapped_column(Price)
    filled_at: Mapped[datetime]
    orderbook_snapshot_id: Mapped[uuid.UUID | None] = _fk("orderbook_snapshots.id", nullable=True)
    # False when the fill was not backed by captured depth (modes A/B); such
    # fills are labelled and excluded from realistic-execution claims.
    depth_backed: Mapped[bool] = mapped_column(Boolean)


class PaperPosition(UUIDPk, Base):
    __tablename__ = "paper_positions"
    __table_args__ = (UniqueConstraint("paper_order_id"),)

    paper_order_id: Mapped[uuid.UUID] = _fk("paper_orders.id", index=False)
    market_outcome_id: Mapped[uuid.UUID] = _fk("market_outcomes.id")
    sport_event_id: Mapped[uuid.UUID | None] = _fk("sport_events.id", nullable=True)
    trader_id: Mapped[uuid.UUID] = _fk("traders.id")
    venue: Mapped[Venue] = enum_column(Venue)
    status: Mapped[PositionStatus] = enum_column(PositionStatus)
    qty: Mapped[Decimal] = mapped_column(Quantity)
    avg_price: Mapped[Decimal] = mapped_column(Price)
    cost_usd: Mapped[Decimal]
    fees_usd: Mapped[Decimal]
    realized_pnl_usd: Mapped[Decimal | None]
    opened_at: Mapped[datetime]
    settled_at: Mapped[datetime | None]
    market_settlement_id: Mapped[uuid.UUID | None] = _fk("market_settlements.id", nullable=True)


class PaperCashLedger(UUIDPk, CreatedAt, Base):
    __tablename__ = "paper_cash_ledger"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    idempotency_key: Mapped[str] = mapped_column(String(200))
    entry_type: Mapped[LedgerEntryType] = enum_column(LedgerEntryType)
    amount_usd: Mapped[Decimal]  # Signed: debits negative, credits positive
    paper_order_id: Mapped[uuid.UUID | None] = _fk("paper_orders.id", nullable=True)
    paper_fill_id: Mapped[uuid.UUID | None] = _fk("paper_fills.id", nullable=True)
    market_settlement_id: Mapped[uuid.UUID | None] = _fk("market_settlements.id", nullable=True)
    memo: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Results and audit
# ---------------------------------------------------------------------------


class MarketSettlement(UUIDPk, Base):
    __tablename__ = "market_settlements"
    __table_args__ = (UniqueConstraint("market_listing_id", "revision"),)

    market_listing_id: Mapped[uuid.UUID] = _fk("market_listings.id", index=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    # Per-outcome settlement value per contract, keyed by venue_outcome_id.
    outcome_values: Mapped[dict[str, Any]] = mapped_column(JsonB)
    result_note: Mapped[str | None] = mapped_column(Text)
    settlement_source: Mapped[str] = mapped_column(String(200))
    source_ts: Mapped[datetime | None]  # When the venue says it settled
    available_at: Mapped[datetime]  # When we could first have known it
    raw_response_id: Mapped[uuid.UUID | None] = _fk("raw_api_responses.id", nullable=True)


class SettlementAdjustment(UUIDPk, CreatedAt, Base):
    """A correction: the original settlement row is never overwritten."""

    __tablename__ = "settlement_adjustments"

    market_settlement_id: Mapped[uuid.UUID] = _fk("market_settlements.id")
    superseded_by_id: Mapped[uuid.UUID] = _fk("market_settlements.id")
    reason: Mapped[str] = mapped_column(Text)


class PaperSettlement(UUIDPk, CreatedAt, Base):
    """Idempotency anchor for settling one paper position against one settlement."""

    __tablename__ = "paper_settlements"
    __table_args__ = (UniqueConstraint("paper_position_id", "market_settlement_id"),)

    paper_position_id: Mapped[uuid.UUID] = _fk("paper_positions.id", index=False)
    market_settlement_id: Mapped[uuid.UUID] = _fk("market_settlements.id")
    result: Mapped[SettlementResult] = enum_column(SettlementResult)
    payout_usd: Mapped[Decimal]


class ModelRun(UUIDPk, Base):
    __tablename__ = "model_runs"

    kind: Mapped[str] = mapped_column(String(60))  # qualification, backtest, ...
    model_version: Mapped[str] = mapped_column(String(40))
    taxonomy_version: Mapped[str] = mapped_column(String(20))
    params: Mapped[dict[str, Any]] = mapped_column(JsonB)
    as_of_cutoff: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    finished_at: Mapped[datetime | None]


class BacktestResult(UUIDPk, CreatedAt, Base):
    __tablename__ = "backtest_results"

    model_run_id: Mapped[uuid.UUID] = _fk("model_runs.id")
    strategy: Mapped[str] = mapped_column(String(100))
    sport: Mapped[Sport | None] = enum_column(Sport, nullable=True)
    market_category: Mapped[MarketCategory | None] = enum_column(MarketCategory, nullable=True)
    venue: Mapped[Venue | None] = enum_column(Venue, nullable=True)
    delay_seconds: Mapped[int | None] = mapped_column(Integer)
    window_start: Mapped[datetime]
    window_end: Mapped[datetime]
    metrics: Mapped[dict[str, Any]] = mapped_column(JsonB)
    limitations: Mapped[str | None] = mapped_column(Text)


class DailyEquity(UUIDPk, Base):
    __tablename__ = "daily_equity"
    __table_args__ = (UniqueConstraint("day", "execution_mode"),)

    day: Mapped[date] = mapped_column(Date)
    execution_mode: Mapped[PaperExecutionMode] = enum_column(PaperExecutionMode)
    equity_usd: Mapped[Decimal]
    realized_pnl_usd: Mapped[Decimal]
    unrealized_pnl_usd: Mapped[Decimal]
    open_exposure_usd: Mapped[Decimal]
    computed_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class AuditEvent(UUIDPk, Base):
    """Append-only audit trail for important state changes."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_entity", "entity_table", "entity_id"),)

    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    actor: Mapped[str] = mapped_column(String(100))  # service or user
    entity_table: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID]
    action: Mapped[str] = mapped_column(String(60))
    before: Mapped[dict[str, Any] | None] = mapped_column(JsonB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JsonB)
    reason: Mapped[str | None] = mapped_column(Text)


# Tables whose rows may never be updated or deleted.
APPEND_ONLY_TABLES = ("audit_events", "trader_qualification_history", "settlement_adjustments")
