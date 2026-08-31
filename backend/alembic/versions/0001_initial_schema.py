"""create initial schema (spec seccion 4)

Revision ID: 0001
Revises:
Create Date: 2026-08-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SKI_LEVELS = ("principiante", "intermedio", "avanzado", "experto")
TRIP_STATUSES = ("preparing", "completed")
DISCIPLINES = ("carving", "freeride", "park", "powder", "moguls", "all_mountain")
ANALYSIS_STATUSES = ("pending", "processed", "failed")


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("ski_level", sa.String(length=20), nullable=False),
        sa.Column("years_skiing", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"ski_level IN ({_in_list(SKI_LEVELS)})", name="ck_users_ski_level"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "trips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="preparing"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"status IN ({_in_list(TRIP_STATUSES)})", name="ck_trips_status"),
    )
    op.create_index("ix_trips_user_id", "trips", ["user_id"])

    op.create_table(
        "video_uploads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("trips.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file_url", sa.String(length=1024), nullable=False),
        sa.Column("discipline_tag", sa.String(length=20), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("analysis_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.CheckConstraint(f"discipline_tag IN ({_in_list(DISCIPLINES)})", name="ck_video_uploads_discipline_tag"),
        sa.CheckConstraint(f"analysis_status IN ({_in_list(ANALYSIS_STATUSES)})", name="ck_video_uploads_analysis_status"),
    )
    op.create_index("ix_video_uploads_user_id", "video_uploads", ["user_id"])
    op.create_index("ix_video_uploads_trip_id", "video_uploads", ["trip_id"])

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "video_id",
            sa.Integer(),
            sa.ForeignKey("video_uploads.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("detected_patterns", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("raw_pose_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_analysis_results_confidence_range"),
    )
    op.create_index("ix_analysis_results_video_id", "analysis_results", ["video_id"], unique=True)

    op.create_table(
        "ski_ratings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("discipline", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("coach_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(f"discipline IN ({_in_list(DISCIPLINES)})", name="ck_ski_ratings_discipline"),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_ski_ratings_score_range"),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_ski_ratings_confidence_range"),
        sa.UniqueConstraint("user_id", "discipline", name="uq_ski_ratings_user_discipline"),
    )
    op.create_index("ix_ski_ratings_user_id", "ski_ratings", ["user_id"])

    op.create_table(
        "training_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "based_on_analysis_id",
            sa.Integer(),
            sa.ForeignKey("analysis_results.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_training_plans_user_id", "training_plans", ["user_id"])
    op.create_index("ix_training_plans_trip_id", "training_plans", ["trip_id"])
    op.create_index("ix_training_plans_based_on_analysis_id", "training_plans", ["based_on_analysis_id"])

    op.create_table(
        "season_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("comparison_video_url", sa.String(length=1024), nullable=False),
        sa.Column("rating_before", sa.JSON(), nullable=False),
        sa.Column("rating_after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_season_reviews_user_id", "season_reviews", ["user_id"])
    op.create_index("ix_season_reviews_trip_id", "season_reviews", ["trip_id"])


def downgrade() -> None:
    op.drop_table("season_reviews")
    op.drop_table("training_plans")
    op.drop_table("ski_ratings")
    op.drop_table("analysis_results")
    op.drop_table("video_uploads")
    op.drop_table("trips")
    op.drop_table("users")
