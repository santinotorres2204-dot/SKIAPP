"""add assessment_results table (physical assessment: 5 tests de prep. fisica)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assessment_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("wall_sit_seconds", sa.Integer(), nullable=False),
        sa.Column("single_leg_squat_left", sa.Integer(), nullable=False),
        sa.Column("single_leg_squat_right", sa.Integer(), nullable=False),
        sa.Column("jump_squat_reps", sa.Integer(), nullable=False),
        sa.Column("plank_seconds", sa.Integer(), nullable=False),
        sa.Column("lateral_bound_reps", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("wall_sit_seconds >= 0", name="ck_assessment_results_wall_sit_range"),
        sa.CheckConstraint("single_leg_squat_left >= 0", name="ck_assessment_results_sls_left_range"),
        sa.CheckConstraint("single_leg_squat_right >= 0", name="ck_assessment_results_sls_right_range"),
        sa.CheckConstraint("jump_squat_reps >= 0", name="ck_assessment_results_jump_squat_range"),
        sa.CheckConstraint("plank_seconds >= 0", name="ck_assessment_results_plank_range"),
        sa.CheckConstraint("lateral_bound_reps >= 0", name="ck_assessment_results_lateral_bound_range"),
    )
    op.create_index("ix_assessment_results_user_id", "assessment_results", ["user_id"])


def downgrade() -> None:
    op.drop_table("assessment_results")
