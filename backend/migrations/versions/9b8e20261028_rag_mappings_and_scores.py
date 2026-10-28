"""RAG map fields, user profile extraction fields, split scores.

Revision ID: 9b8e20261028
Revises: 7a3c20261024
"""
from alembic import op
import sqlalchemy as sa

revision = '9b8e20261028'
down_revision = '7a3c20261024'
branch_labels = None
depends_on = None


def upgrade():
    # Align physical column name with the RAG team's interface. Preserve all prior values.
    op.alter_column('announcements', 'support_types_json', new_column_name='support_types', existing_type=sa.JSON())
    op.add_column('announcements', sa.Column('region', sa.String(20), nullable=True))
    op.add_column('announcements', sa.Column('seoul_gu', sa.Text(), nullable=True))
    op.add_column('announcements', sa.Column('has_text', sa.Boolean(), nullable=True))
    op.create_index('ix_announcements_region', 'announcements', ['region'])
    op.add_column('user_requests', sa.Column('startup_months', sa.Integer(), nullable=True))
    op.add_column('user_requests', sa.Column('gender', sa.String(20), nullable=True))
    op.add_column('user_requests', sa.Column('is_registered', sa.Boolean(), nullable=True))
    op.add_column('user_requests', sa.Column('startup_stage', sa.String(50), nullable=True))
    op.add_column('user_requests', sa.Column('business_type', sa.String(255), nullable=True))
    op.add_column('user_requests', sa.Column('needed_support', sa.String(100), nullable=True))
    op.add_column('user_requests', sa.Column('funding_gap', sa.Integer(), nullable=True))
    op.execute(sa.text('UPDATE user_requests SET startup_stage = biz_stage WHERE startup_stage IS NULL'))
    op.add_column('match_results', sa.Column('search_score', sa.Float(), nullable=True))
    op.add_column('match_results', sa.Column('judgment_score', sa.Float(), nullable=True))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead.')
