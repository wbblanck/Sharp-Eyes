"""SQLAlchemy declarative base and shared column types."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, MetaData, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Enum as SAEnum

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Prices are probabilities in [0, 1]; money is USD. Both are exact decimals.
Price = Numeric(12, 6)
Money = Numeric(20, 6)
Quantity = Numeric(24, 6)

JsonB = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_cls: type[StrEnum], **kwargs: Any) -> Mapped[Any]:
    """A VARCHAR + CHECK enum column. Non-native so adding values is a simple migration."""
    return mapped_column(
        SAEnum(
            enum_cls,
            native_enum=False,
            create_constraint=True,
            length=40,
            name=enum_cls.__name__.lower(),
            values_callable=lambda e: [m.value for m in e],
            validate_strings=True,
        ),
        **kwargs,
    )


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {  # noqa: RUF012
        datetime: DateTime(timezone=True),
        Decimal: Money,
        str: String(),
        dict[str, Any]: JsonB,
        uuid.UUID: PG_UUID(as_uuid=True),
    }


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
