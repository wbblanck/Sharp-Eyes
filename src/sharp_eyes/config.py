"""Application configuration.

Non-secret settings come from a YAML file (``config/default.yaml`` by default).
Secrets come only from environment variables and are held as ``SecretStr`` so
they are never printed in reprs or logs.
"""

from __future__ import annotations

import os
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


class ExecutionMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class StakeMode(StrEnum):
    FIXED_USD = "fixed_usd"
    FIXED_UNITS = "fixed_units"


class PaperExecutionMode(StrEnum):
    """Spec 10.2: modes A, B and C."""

    IMMEDIATE_INDICATIVE = "immediate_indicative"
    DELAYED_QUOTE = "delayed_quote"
    DEPTH_AWARE = "depth_aware"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExecutionConfig(_Frozen):
    mode: ExecutionMode = ExecutionMode.PAPER
    live_orders_enabled: bool = False

    @model_validator(mode="after")
    def _live_is_not_available(self) -> ExecutionConfig:
        # Live execution does not exist in this release (spec 2.2, 19). A config
        # file cannot turn it on; enabling it requires the SC-022 readiness
        # assessment, new code, and explicit user authorization.
        if self.mode is not ExecutionMode.PAPER or self.live_orders_enabled:
            raise ValueError(
                "live execution is disabled in this release; "
                "execution.mode must be 'paper' and live_orders_enabled must be false"
            )
        return self


class PaperConfig(_Frozen):
    stake_mode: StakeMode = StakeMode.FIXED_USD
    fixed_stake_usd: Decimal = Decimal("10.00")
    unit_value_usd: Decimal = Decimal("10.00")
    units_per_signal: Decimal = Decimal("1.0")
    bankroll_usd: Decimal = Decimal("1000.00")
    execution_mode: PaperExecutionMode = PaperExecutionMode.DELAYED_QUOTE

    @field_validator("fixed_stake_usd", "unit_value_usd", "units_per_signal", "bankroll_usd")
    @classmethod
    def _positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("must be positive")
        return v

    def stake_usd(self) -> Decimal:
        """The paper stake per signal in USD."""
        if self.stake_mode is StakeMode.FIXED_USD:
            return self.fixed_stake_usd
        return self.unit_value_usd * self.units_per_signal


class RiskConfig(_Frozen):
    min_net_ev: Decimal = Decimal("0.01")
    max_signal_age_seconds: int = Field(default=30, gt=0)
    require_exact_contract_match: bool = True
    max_per_event_exposure_usd: Decimal = Decimal("30.00")
    max_per_trader_exposure_usd: Decimal = Decimal("50.00")
    max_total_open_exposure_usd: Decimal = Decimal("500.00")

    @field_validator("require_exact_contract_match")
    @classmethod
    def _exact_only(cls, v: bool) -> bool:
        # Spec 7.2: only EXACT matches may be auto-executed in the initial release.
        if not v:
            raise ValueError("require_exact_contract_match must be true in this release")
        return v


class QualificationConfig(_Frozen):
    min_settled_wagers: int = Field(default=200, ge=1)
    min_distinct_events: int = Field(default=30, ge=1)


class CadenceConfig(_Frozen):
    polymarket_trade_ingestion: int = Field(default=10, gt=0)
    market_catalog_refresh: int = Field(default=300, gt=0)
    qualification_recalc: int = Field(default=1800, gt=0)
    settlement_polling: int = Field(default=600, gt=0)
    health_check: int = Field(default=60, gt=0)


class BookScope(StrEnum):
    CORE = "core"  # Full-game moneyline, spread, total (the first milestone)
    GAME = "game"  # Every non-prop game market, including halves and quarters
    ALL = "all"  # Everything in the catalog, props included


class CaptureTier(_Frozen):
    """Book polling interval for games kicking off within ``within_minutes``."""

    within_minutes: int = Field(gt=0)
    books_seconds: int = Field(gt=0)


class VenueCaptureConfig(_Frozen):
    enabled: bool = True
    rate_per_second: float = Field(default=5.0, gt=0)
    concurrency: int = Field(default=4, ge=1)
    book_scope: BookScope = BookScope.CORE
    trades_seconds: int = Field(default=30, gt=0)
    max_levels: int = Field(default=50, ge=1)


class PolymarketCaptureConfig(VenueCaptureConfig):
    data_rate_per_second: float = Field(default=10.0, gt=0)  # Data API: 300 req / 10 s
    clob_rate_per_second: float = Field(default=10.0, gt=0)
    status_seconds: int = Field(default=10, gt=0)
    trade_overlap_seconds: int = Field(default=600, ge=0)
    backfill_history: bool = True


class KalshiCaptureConfig(VenueCaptureConfig):
    series: tuple[str, ...] = ("KXNFLGAME", "KXNFLSPREAD", "KXNFLTOTAL", "KXNFLTEAMTOTAL")


class NovigCaptureConfig(VenueCaptureConfig):
    market_types: tuple[str, ...] = (
        "MONEY",
        "SPREAD",
        "TOTAL",
        "TEAM_TOTAL",
        "SPREAD_1H",
        "TOTAL_1H",
    )


class CaptureConfig(_Frozen):
    """Phase 0 capture worker (NFL catalogs, books and trades)."""

    # Games that kicked off up to this long ago are still captured (in play).
    window_past_hours: int = Field(default=6, ge=0)
    window_future_days: int = Field(default=8, gt=0)
    catalog_seconds: int = Field(default=300, gt=0)
    # Ordered nearest-first; games further out than the last tier use cold_books_seconds.
    tiers: tuple[CaptureTier, ...] = (
        CaptureTier(within_minutes=180, books_seconds=15),
        CaptureTier(within_minutes=36 * 60, books_seconds=60),
    )
    cold_books_seconds: int = Field(default=600, gt=0)
    polymarket: PolymarketCaptureConfig = PolymarketCaptureConfig(
        book_scope=BookScope.GAME, trades_seconds=2, rate_per_second=4.0
    )
    polymarket_us: VenueCaptureConfig = VenueCaptureConfig(rate_per_second=10.0, concurrency=8)
    kalshi: KalshiCaptureConfig = KalshiCaptureConfig(rate_per_second=4.0)
    novig: NovigCaptureConfig = NovigCaptureConfig(rate_per_second=2.0, max_levels=20)

    def books_interval(self, minutes_to_start: float) -> int:
        for tier in sorted(self.tiers, key=lambda t: t.within_minutes):
            if minutes_to_start <= tier.within_minutes:
                return tier.books_seconds
        return self.cold_books_seconds


class AppConfig(_Frozen):
    execution: ExecutionConfig = ExecutionConfig()
    paper: PaperConfig = PaperConfig()
    risk: RiskConfig = RiskConfig()
    qualification: QualificationConfig = QualificationConfig()
    cadence_seconds: CadenceConfig = CadenceConfig()
    capture: CaptureConfig = CaptureConfig()


class Secrets(BaseSettings):
    """Secrets read from the environment only. All are optional in paper mode."""

    model_config = SettingsConfigDict(env_prefix="SHARP_EYES_", extra="ignore")

    database_url: SecretStr | None = None
    kalshi_api_key_id: SecretStr | None = None
    kalshi_private_key_path: SecretStr | None = None
    novig_key_id: SecretStr | None = None
    novig_private_key_path: SecretStr | None = None
    polymarket_us_api_key: SecretStr | None = None


def load_config(path: str | os.PathLike[str] | None = None) -> AppConfig:
    """Load the YAML config. ``SHARP_EYES_CONFIG`` overrides the default path."""
    resolved = Path(path or os.environ.get("SHARP_EYES_CONFIG") or DEFAULT_CONFIG_PATH)
    raw: Any = yaml.safe_load(resolved.read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"config file {resolved} must contain a mapping")
    return AppConfig.model_validate(raw)


def load_secrets() -> Secrets:
    return Secrets()
