"""Add physical Korean category label and 9 integer 0/1 category columns.

Revision ID: c1a02c261028
Revises: 9b8e20261028

The migration backfills existing records from support_types, so existing DBs retain
all 342 category assignments. The original team CSV can be revalidated/imported
with scripts.import_mappings after upgrading.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c1a02c261028'
down_revision = '9b8e20261028'
branch_labels = None
depends_on = None

CATEGORY_NAMES = ('자금','교육·컨설팅','공간·시설','홍보·판매','인력','기술개발','해외진출','제도·인증','기타')


def upgrade():
    op.add_column('announcements', sa.Column('카테고리', sa.Text(), nullable=True))
    for name in CATEGORY_NAMES:
        op.add_column('announcements', sa.Column(name, sa.Integer(), nullable=False, server_default=sa.text('0')))

    bind=op.get_bind()
    announcements = sa.table('announcements', sa.column('announcement_id', sa.String(32)), sa.column('support_types', sa.JSON()))
    rows=bind.execute(sa.select(announcements.c.announcement_id, announcements.c.support_types)).all()
    # SQLAlchemy handles JSON/JSONB/SQLite deserialization via type metadata.
    stmt=sa.text('UPDATE announcements SET "카테고리"=:label, "자금"=:v0, "교육·컨설팅"=:v1, "공간·시설"=:v2, "홍보·판매"=:v3, "인력"=:v4, "기술개발"=:v5, "해외진출"=:v6, "제도·인증"=:v7, "기타"=:v8 WHERE announcement_id=:id')
    params=[]
    import json
    for aid, raw in rows:
        if isinstance(raw,str):
            raw=json.loads(raw) if raw else []
        if raw is None: raw=[]
        if not isinstance(raw,list):
            raise ValueError(f'{aid} support_types is not a JSON array')
        invalid=set(raw)-set(CATEGORY_NAMES)
        if invalid:
            raise ValueError(f'{aid} unknown categories {sorted(invalid)}')
        cats=[name for name in CATEGORY_NAMES if name in raw]
        data={'id':aid,'label':', '.join(cats)}
        data.update({f'v{i}':int(name in cats) for i,name in enumerate(CATEGORY_NAMES)})
        params.append(data)
    if params: bind.execute(stmt,params)


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore the original DB backup instead.')
