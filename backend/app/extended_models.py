"""ERD v2 workflow entities. Default demo requests are not persisted (privacy)."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, Float, String, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
from app.models import FlexibleJSON

class UserRequest(Base):
    __tablename__ = 'user_requests'
    request_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    profile_json: Mapped[dict | None] = mapped_column(FlexibleJSON)
    age: Mapped[int | None] = mapped_column(Integer)
    startup_months: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(20))
    is_registered: Mapped[bool | None] = mapped_column(Boolean)
    sido: Mapped[str | None] = mapped_column(String(70))
    sigungu: Mapped[str | None] = mapped_column(String(70))
    biz_stage: Mapped[str | None] = mapped_column(String(40))
    startup_stage: Mapped[str | None] = mapped_column(String(50))
    business_type: Mapped[str | None] = mapped_column(String(255))
    needed_support: Mapped[str | None] = mapped_column(String(100))
    funding_gap: Mapped[int | None] = mapped_column(Integer)  # 만원, not KRW
    industry_ksic_json: Mapped[list | None] = mapped_column(FlexibleJSON)
    needs_json: Mapped[list | None] = mapped_column(FlexibleJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    runs: Mapped[list['MatchRun']] = relationship(back_populates='request', cascade='all, delete-orphan')

class MatchRun(Base):
    __tablename__ = 'match_runs'
    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey('user_requests.request_id'), nullable=False, index=True)
    execution_status: Mapped[str] = mapped_column(String(30), nullable=False)
    data_source: Mapped[str | None] = mapped_column(String(40))
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    search_version: Mapped[str | None] = mapped_column(String(40))
    judge_version: Mapped[str | None] = mapped_column(String(40))
    parser_version: Mapped[str | None] = mapped_column(String(40))
    schema_version: Mapped[str | None] = mapped_column(String(20))
    data_snapshot: Mapped[str | None] = mapped_column(String(80))
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    cost_currency: Mapped[str | None] = mapped_column(String(10))
    summary_json: Mapped[dict | None] = mapped_column(FlexibleJSON)
    coverage_json: Mapped[dict | None] = mapped_column(FlexibleJSON)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    request: Mapped[UserRequest] = relationship(back_populates='runs')
    results: Mapped[list['MatchResult']] = relationship(back_populates='run', cascade='all, delete-orphan')

class MatchResult(Base):
    __tablename__ = 'match_results'
    __table_args__ = (UniqueConstraint('run_id', 'announcement_id', name='uq_match_run_announcement'),)
    result_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('match_runs.run_id'), nullable=False, index=True)
    announcement_id: Mapped[str] = mapped_column(ForeignKey('announcements.announcement_id'), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    verdict_source: Mapped[str] = mapped_column(String(30), nullable=False, default='demo_unverified')
    score: Mapped[float | None] = mapped_column(Float)  # Legacy frontend display score
    search_score: Mapped[float | None] = mapped_column(Float)
    judgment_score: Mapped[float | None] = mapped_column(Float)
    rank_number: Mapped[int | None] = mapped_column(Integer)
    headline: Mapped[str | None] = mapped_column(Text)
    reasons_json: Mapped[list | None] = mapped_column(FlexibleJSON)
    cautions_json: Mapped[list | None] = mapped_column(FlexibleJSON)
    exceptions_json: Mapped[list | None] = mapped_column(FlexibleJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    run: Mapped[MatchRun] = relationship(back_populates='results')
    checks: Mapped[list['ConditionCheck']] = relationship(back_populates='result', cascade='all, delete-orphan')

class ConditionCheck(Base):
    __tablename__ = 'condition_checks'
    check_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(ForeignKey('match_results.result_id'), nullable=False, index=True)
    condition_id: Mapped[int | None] = mapped_column(ForeignKey('conditions.condition_id'), index=True)
    condition_path: Mapped[str | None] = mapped_column(String(255))
    check_status: Mapped[str] = mapped_column(String(30), nullable=False)
    user_value_json: Mapped[dict | list | None] = mapped_column(FlexibleJSON)
    required_value_json: Mapped[dict | list | None] = mapped_column(FlexibleJSON)
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    evidence_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evidence_start: Mapped[int | None] = mapped_column(Integer)
    evidence_end: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    result: Mapped[MatchResult] = relationship(back_populates='checks')
