"""add trick_cards and freeride_runs (park/freeride self-registro manual)

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trick_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trick_name", sa.String(length=255), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("execution_score", sa.Integer(), nullable=False),
        sa.Column("landing_score", sa.Integer(), nullable=False),
        sa.Column("style_score", sa.Integer(), nullable=False),
        sa.Column("consistency_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 10", name="ck_trick_cards_difficulty_range"),
        sa.CheckConstraint("execution_score BETWEEN 0 AND 100", name="ck_trick_cards_execution_range"),
        sa.CheckConstraint("landing_score BETWEEN 0 AND 100", name="ck_trick_cards_landing_range"),
        sa.CheckConstraint("style_score BETWEEN 0 AND 100", name="ck_trick_cards_style_range"),
        sa.CheckConstraint("consistency_score BETWEEN 0 AND 100", name="ck_trick_cards_consistency_range"),
    )
    op.create_index("ix_trick_cards_video_id", "trick_cards", ["video_id"])
    op.create_index("ix_trick_cards_user_id", "trick_cards", ["user_id"])

    op.create_table(
        "freeride_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_name", sa.String(length=255), nullable=False),
        sa.Column("vertical_m", sa.Float(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("max_gradient", sa.Float(), nullable=False),
        sa.Column("flow_score", sa.Integer(), nullable=False),
        sa.Column("control_score", sa.Integer(), nullable=False),
        sa.Column("line_choice_score", sa.Integer(), nullable=False),
        sa.Column("difficulty_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("flow_score BETWEEN 0 AND 100", name="ck_freeride_runs_flow_range"),
        sa.CheckConstraint("control_score BETWEEN 0 AND 100", name="ck_freeride_runs_control_range"),
        sa.CheckConstraint("line_choice_score BETWEEN 0 AND 100", name="ck_freeride_runs_line_choice_range"),
        sa.CheckConstraint("difficulty_score BETWEEN 0 AND 100", name="ck_freeride_runs_difficulty_range"),
    )
    op.create_index("ix_freeride_runs_video_id", "freeride_runs", ["video_id"])
    op.create_index("ix_freeride_runs_user_id", "freeride_runs", ["user_id"])


def downgrade() -> None:
    op.drop_table("freeride_runs")
    op.drop_table("trick_cards")
