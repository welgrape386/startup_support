"""add self_funding_json and info_tracks_json columns to announcements

Revision ID: d5e02c261117
Revises: c1a02c261028
Create Date: 2026-11-17 23:00:00.000000

"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
import json

# revision identifiers, used by Alembic.
revision = 'd5e02c261117'
down_revision = 'c1a02c261028'
branch_labels = None
depends_on = None


class FlexibleJSONType(sa.TypeDecorator):
    impl = sa.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value


J = FlexibleJSONType()


def upgrade() -> None:
    for n, t in [
        ('self_funding_json', J),
        ('info_tracks_json', J),
    ]:
        op.add_column('announcements', sa.Column(n, t, nullable=True))


def downgrade() -> None:
    # SQLite doesn't support DROP COLUMN in older versions, skip for SQLite
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        op.drop_column('announcements', 'info_tracks_json')
        op.drop_column('announcements', 'self_funding_json')
