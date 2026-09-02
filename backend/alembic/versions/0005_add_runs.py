"""add runs table (ride mode: gps tracking de bajadas)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("max_speed_kmh", sa.Float(), nullable=True),
        sa.Column("avg_speed_kmh", sa.Float(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("elevation_gain_m", sa.Float(), nullable=True),
        sa.Column("elevation_loss_m", sa.Float(), nullable=True),
        sa.Column("gps_track", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("duration_seconds >= 0", name="ck_runs_duration_seconds_range"),
        sa.CheckConstraint("max_speed_kmh >= 0", name="ck_runs_max_speed_range"),
        sa.CheckConstraint("avg_speed_kmh >= 0", name="ck_runs_avg_speed_range"),
        sa.CheckConstraint("distance_km >= 0", name="ck_runs_distance_km_range"),
        sa.CheckConstraint("elevation_gain_m >= 0", name="ck_runs_elevation_gain_range"),
        sa.CheckConstraint("elevation_loss_m >= 0", name="ck_runs_elevation_loss_range"),
    )
    op.create_index("ix_runs_user_id", "runs", ["user_id"])


def downgrade() -> None:
    op.drop_table("runs")
