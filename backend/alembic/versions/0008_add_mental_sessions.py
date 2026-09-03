"""add mental_sessions table

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-03

"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'mental_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('fear_type', sa.Enum('velocidad', 'pendiente', 'caidas', 'exposicion', 'otro', name='feartype'), nullable=False),
        sa.Column('intensity_before', sa.Integer(), nullable=False),
        sa.Column('intensity_after', sa.Integer(), nullable=True),
        sa.Column('technique_used', sa.Enum('respiracion', 'visualizacion', 'self_talk', 'escalera', name='technique'), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
    )

def downgrade():
    op.drop_table('mental_sessions')
    op.execute("DROP TYPE IF EXISTS feartype")
    op.execute("DROP TYPE IF EXISTS technique")
