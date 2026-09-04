"""add terrain_tag to video_uploads

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TERRAIN_TAGS = ("pista_pisada", "powder", "hielo", "mixto")


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.add_column("video_uploads", sa.Column("terrain_tag", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_video_uploads_terrain_tag",
        "video_uploads",
        f"terrain_tag IS NULL OR terrain_tag IN ({_in_list(TERRAIN_TAGS)})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_video_uploads_terrain_tag", "video_uploads", type_="check")
    op.drop_column("video_uploads", "terrain_tag")
