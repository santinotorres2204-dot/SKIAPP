"""add day_logs table (etapa 2: day recap)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "day_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("elevation_gain_m", sa.Integer(), nullable=False),
        sa.Column("max_speed_kmh", sa.Float(), nullable=False),
        sa.Column("runs_count", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("distance_km >= 0", name="ck_day_logs_distance_km_range"),
        sa.CheckConstraint("elevation_gain_m >= 0", name="ck_day_logs_elevation_gain_range"),
        sa.CheckConstraint("max_speed_kmh >= 0", name="ck_day_logs_max_speed_range"),
        sa.CheckConstraint("runs_count >= 0", name="ck_day_logs_runs_count_range"),
    )
    op.create_index("ix_day_logs_trip_id", "day_logs", ["trip_id"])
    op.create_index("ix_day_logs_user_id", "day_logs", ["user_id"])


def downgrade() -> None:
    op.drop_table("day_logs")
