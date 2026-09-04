"""add sport_type to video_uploads

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SPORT_TYPES = ("ski", "snowboard")


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.add_column("video_uploads", sa.Column("sport_type", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_video_uploads_sport_type",
        "video_uploads",
        f"sport_type IS NULL OR sport_type IN ({_in_list(SPORT_TYPES)})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_video_uploads_sport_type", "video_uploads", type_="check")
    op.drop_column("video_uploads", "sport_type")
