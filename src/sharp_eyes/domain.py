"""Shared domain enumerations used by the schema and the services."""

from __future__ import annotations

from enum import StrEnum


class Venue(StrEnum):
    # International Polymarket (polymarket.com): the source of identifiable trader
    # activity. US persons are close-only there, so it is never a US execution venue.
    POLYMARKET = "POLYMARKET"
    # Polymarket US (polymarket.us), the CFTC-regulated exchange. Separate API,
    # separate markets, no public per-trader activity.
    POLYMARKET_US = "POLYMARKET_US"
    KALSHI = "KALSHI"
    NOVIG = "NOVIG"
    # Non-venue sources (schedules, results).
    SPORTS_DATA = "SPORTS_DATA"


class IngestionStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ActivityClass(StrEnum):
    """Spec 6.1: how an observed source record is classified."""

    NEW_TRADE = "NEW_TRADE"
    PREVIOUSLY_OBSERVED = "PREVIOUSLY_OBSERVED"
    HISTORICAL_BACKFILL = "HISTORICAL_BACKFILL"
    DUPLICATE = "DUPLICATE"
    CORRECTION = "CORRECTION"
    POSITION_UPDATE = "POSITION_UPDATE"
    REDUCTION = "REDUCTION"  # Sale or reduction of an existing position
    SETTLEMENT = "SETTLEMENT"  # Redemption / settlement activity
    UNCLASSIFIED = "UNCLASSIFIED"


class TradeSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class QualificationStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    PROVISIONAL = "PROVISIONAL"
    QUALIFIED = "QUALIFIED"
    SUSPENDED = "SUSPENDED"
    DISQUALIFIED = "DISQUALIFIED"


class MatchState(StrEnum):
    """Spec 7.2."""

    EXACT = "EXACT"
    EQUIVALENT_WITH_RULE_DIFFERENCE = "EQUIVALENT_WITH_RULE_DIFFERENCE"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_EQUIVALENT = "NOT_EQUIVALENT"
    UNAVAILABLE = "UNAVAILABLE"


class ListingStatus(StrEnum):
    UNOPENED = "UNOPENED"
    OPEN = "OPEN"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"
    SETTLED = "SETTLED"
    VOIDED = "VOIDED"
    UNKNOWN = "UNKNOWN"


class BookSide(StrEnum):
    BID = "BID"
    ASK = "ASK"


class SignalState(StrEnum):
    """Spec 10.3 execution state machine, signal half."""

    SIGNAL_DETECTED = "SIGNAL_DETECTED"
    SIGNAL_VALIDATED = "SIGNAL_VALIDATED"
    CONTRACT_MATCHED = "CONTRACT_MATCHED"
    PRICE_EVALUATED = "PRICE_EVALUATED"
    RISK_APPROVED = "RISK_APPROVED"
    PAPER_ORDER_CREATED = "PAPER_ORDER_CREATED"
    REJECTED = "REJECTED"
    HELD_FOR_REVIEW = "HELD_FOR_REVIEW"


class PaperOrderState(StrEnum):
    """Spec 10.3 execution state machine, order half."""

    CREATED = "CREATED"
    EXPIRED = "EXPIRED"
    UNFILLED = "UNFILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"


class PositionStatus(StrEnum):
    OPEN = "OPEN"
    SETTLED = "SETTLED"


class SettlementResult(StrEnum):
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"
    VOID = "VOID"
    FIXED_PRICE = "FIXED_PRICE"  # Settled at a non-binary price, e.g. 0.50


class LedgerEntryType(StrEnum):
    DEPOSIT = "DEPOSIT"
    STAKE = "STAKE"
    FEE = "FEE"
    PAYOUT = "PAYOUT"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"
