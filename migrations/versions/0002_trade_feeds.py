"""per-feed first sighting of each trade

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24 17:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("api_observed_at", "ws_observed_at"):
        op.add_column(
            "trades", sa.Column(name, sa.DateTime(timezone=True), nullable=True), schema="capture"
        )
    # Every row so far came from the REST polls.
    op.execute("UPDATE capture.trades SET api_observed_at = observed_at")


def downgrade() -> None:
    for name in ("ws_observed_at", "api_observed_at"):
        op.drop_column("trades", name, schema="capture")
