"""Alembic environment. The database URL comes from SHARP_EYES_DATABASE_URL."""

from __future__ import annotations

from alembic import context
from sqlalchemy import text

from sharp_eyes.capture.schema import SCHEMA, metadata
from sharp_eyes.db.session import make_engine

target_metadata = metadata


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    # Only the capture schema is migration-managed so far; the Phase 1 canonical
    # schema gets its own migrations when it is finalised.
    if type_ == "schema":
        return name == SCHEMA
    return True


def run_migrations_online() -> None:
    engine = make_engine()
    with engine.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            version_table_schema=SCHEMA,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("offline migrations are not supported; set SHARP_EYES_DATABASE_URL")
run_migrations_online()
