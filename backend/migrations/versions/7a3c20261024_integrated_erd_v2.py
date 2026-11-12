"""Expand 4-table DB to integrated ERD v2 without deleting announcement data.

Revision ID: 7a3c20261024
Revises: 20df4fd96723
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='7a3c20261024'
down_revision='20df4fd96723'
branch_labels=None
depends_on=None
J = sa.JSON().with_variant(JSONB(), 'postgresql')

def upgrade():
    for n,t in [
        ('support_types_json',J),('amount_max_manwon',sa.Integer()),('total_budget_text',sa.Text()),
        ('interest_rate',sa.String(120)),('support_detail',sa.Text()),('status',sa.String(30)),
        ('duplicate_policy_json',J),('submission_docs_json',J),('bonus_points_json',J),('rounds_json',J),
        ('reviewed',sa.Boolean()),('collected_at',sa.DateTime())]:
        op.add_column('announcements',sa.Column(n,t,nullable=True))
    op.execute(sa.text('UPDATE announcements SET reviewed = 0 WHERE reviewed IS NULL'))

    # The initial SQLite schema had an unnamed UNIQUE(announcement_id) on texts.
    # Rebuild once with all existing rows/IDs preserved, then enable multi-file texts.
    op.create_table('texts_v2_tmp',
        sa.Column('text_id',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('announcement_id',sa.String(32),sa.ForeignKey('announcements.announcement_id'),nullable=False),
        sa.Column('content',sa.Text()),sa.Column('source_format',sa.String(20)),
        sa.Column('source_file_name',sa.Text()),sa.Column('extraction_status',sa.String(80),nullable=False),
        sa.Column('suspected_incomplete',sa.Boolean(),nullable=False),sa.Column('extraction_error',sa.Text()),
        sa.Column('extracted_at',sa.DateTime()),
        sa.Column('file_id',sa.Integer(),sa.ForeignKey('files.file_id'),nullable=True),
        sa.Column('is_primary',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('source_kind',sa.String(30)),sa.Column('section_name',sa.String(100))
    )
    op.execute(sa.text('''INSERT INTO texts_v2_tmp (text_id,announcement_id,content,source_format,source_file_name,extraction_status,suspected_incomplete,extraction_error,extracted_at,is_primary)
        SELECT text_id,announcement_id,content,source_format,source_file_name,extraction_status,suspected_incomplete,extraction_error,extracted_at,1 FROM texts'''))
    op.drop_table('texts')
    op.rename_table('texts_v2_tmp','texts')
    op.create_index('ix_texts_announcement_id','texts',['announcement_id'])

    for n,t in [('source_text_id',sa.Integer()),('model_name',sa.String(100)),('prompt_version',sa.String(50)),('quote_validation_status',sa.String(30))]:
        op.add_column('conditions',sa.Column(n,t))
    # SQLite won't safely add a foreign key to an existing populated table without rebuilding.
    # SQLAlchemy model provides the source_text_id FK for fresh DBs; application enforces existence locally.
    if op.get_bind().dialect.name!='sqlite':
        op.create_foreign_key('fk_conditions_source_text_id','conditions','texts',['source_text_id'],['text_id'])

    op.create_table('user_requests',
        sa.Column('request_id',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('input_text',sa.Text(),nullable=False),sa.Column('profile_json',J),
        sa.Column('age',sa.Integer()),sa.Column('sido',sa.String(70)),sa.Column('sigungu',sa.String(70)),
        sa.Column('biz_stage',sa.String(40)),sa.Column('industry_ksic_json',J),sa.Column('needs_json',J),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_table('match_runs',
        sa.Column('run_id',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('request_id',sa.Integer(),sa.ForeignKey('user_requests.request_id'),nullable=False),
        sa.Column('execution_status',sa.String(30),nullable=False),
        sa.Column('data_source',sa.String(40)),sa.Column('model_name',sa.String(100)),
        sa.Column('prompt_version',sa.String(50)),sa.Column('search_version',sa.String(40)),
        sa.Column('judge_version',sa.String(40)),sa.Column('parser_version',sa.String(40)),
        sa.Column('schema_version',sa.String(20)),sa.Column('data_snapshot',sa.String(80)),
        sa.Column('processing_time_ms',sa.Integer()),sa.Column('input_tokens',sa.Integer()),
        sa.Column('output_tokens',sa.Integer()),sa.Column('estimated_cost',sa.Float()),
        sa.Column('cost_currency',sa.String(10)),sa.Column('summary_json',J),sa.Column('coverage_json',J),
        sa.Column('started_at',sa.DateTime(),nullable=False),sa.Column('completed_at',sa.DateTime()))
    op.create_index('ix_match_runs_request_id','match_runs',['request_id'])
    op.create_table('match_results',
        sa.Column('result_id',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('run_id',sa.Integer(),sa.ForeignKey('match_runs.run_id'),nullable=False),
        sa.Column('announcement_id',sa.String(32),sa.ForeignKey('announcements.announcement_id'),nullable=False),
        sa.Column('verdict',sa.String(30),nullable=False),
        sa.Column('verdict_source',sa.String(30),nullable=False),
        sa.Column('score',sa.Float()),sa.Column('rank_number',sa.Integer()),
        sa.Column('headline',sa.Text()),sa.Column('reasons_json',J),sa.Column('cautions_json',J),
        sa.Column('exceptions_json',J),sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('run_id','announcement_id',name='uq_match_run_announcement'))
    op.create_index('ix_match_results_run_id','match_results',['run_id'])
    op.create_index('ix_match_results_announcement_id','match_results',['announcement_id'])
    op.create_table('condition_checks',
        sa.Column('check_id',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('result_id',sa.Integer(),sa.ForeignKey('match_results.result_id'),nullable=False),
        sa.Column('condition_id',sa.Integer(),sa.ForeignKey('conditions.condition_id')),
        sa.Column('condition_path',sa.String(255)),sa.Column('check_status',sa.String(30),nullable=False),
        sa.Column('user_value_json',J),sa.Column('required_value_json',J),
        sa.Column('reason',sa.Text()),sa.Column('evidence_quote',sa.Text()),
        sa.Column('evidence_verified',sa.Boolean(),nullable=False),
        sa.Column('evidence_start',sa.Integer()),sa.Column('evidence_end',sa.Integer()),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_condition_checks_result_id','condition_checks',['result_id'])
    op.create_index('ix_condition_checks_condition_id','condition_checks',['condition_id'])

def downgrade():
    raise RuntimeError('Migration downgrade intentionally blocked to protect the existing 342 announcement records. Restore the pre-upgrade backup instead.')
