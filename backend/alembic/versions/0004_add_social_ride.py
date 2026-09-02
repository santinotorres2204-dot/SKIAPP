"""add trip join_code and trip_participants (etapa 2: social ride)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("join_code", sa.String(length=12), nullable=True))
    op.create_index("ix_trips_join_code", "trips", ["join_code"], unique=True)

    op.create_table(
        "trip_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("trip_id", "user_id", name="uq_trip_participants_trip_user"),
    )
    op.create_index("ix_trip_participants_trip_id", "trip_participants", ["trip_id"])
    op.create_index("ix_trip_participants_user_id", "trip_participants", ["user_id"])


def downgrade() -> None:
    op.drop_table("trip_participants")
    op.drop_index("ix_trips_join_code", table_name="trips")
    op.drop_column("trips", "join_code")
