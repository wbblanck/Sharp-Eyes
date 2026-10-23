"""Engine and session factories."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from sharp_eyes.config import load_secrets


class DatabaseNotConfiguredError(RuntimeError):
    pass


def database_url() -> str:
    secret = load_secrets().database_url
    if secret is None:
        raise DatabaseNotConfiguredError("SHARP_EYES_DATABASE_URL is not set")
    return secret.get_secret_value()


def make_engine(url: str | None = None) -> Engine:
    # hide_parameters keeps bound values (which can include payloads) out of error logs.
    return create_engine(url or database_url(), pool_pre_ping=True, hide_parameters=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
