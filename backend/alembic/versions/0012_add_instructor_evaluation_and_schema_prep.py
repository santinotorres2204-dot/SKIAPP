"""add instructor_evaluations, consent_for_improvement y analysis_version

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "video_uploads",
        sa.Column("consent_for_improvement", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "analysis_results",
        sa.Column("analysis_version", sa.String(length=50), nullable=True),
    )

    op.create_table(
        "instructor_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asimetria_severity", sa.String(length=20), nullable=True),
        sa.Column("asimetria_sample_size", sa.Integer(), nullable=True),
        sa.Column("balance_severity", sa.String(length=20), nullable=True),
        sa.Column("balance_sample_size", sa.Integer(), nullable=True),
        sa.Column("inconsistencia_severity", sa.String(length=20), nullable=True),
        sa.Column("inconsistencia_sample_size", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("instructor_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "asimetria_severity IS NULL OR asimetria_severity IN ('baja', 'media', 'alta')",
            name="ck_instructor_evaluations_asimetria_severity",
        ),
        sa.CheckConstraint(
            "balance_severity IS NULL OR balance_severity IN ('baja', 'media', 'alta')",
            name="ck_instructor_evaluations_balance_severity",
        ),
        sa.CheckConstraint(
            "inconsistencia_severity IS NULL OR inconsistencia_severity IN ('baja', 'media', 'alta')",
            name="ck_instructor_evaluations_inconsistencia_severity",
        ),
    )
    op.create_index("ix_instructor_evaluations_video_id", "instructor_evaluations", ["video_id"], unique=True)


def downgrade() -> None:
    op.drop_table("instructor_evaluations")
    op.drop_column("analysis_results", "analysis_version")
    op.drop_column("video_uploads", "consent_for_improvement")
