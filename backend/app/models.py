"""Four initial tables; raw condition JSON uses PostgreSQL JSONB in production."""
from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

FlexibleJSON = JSON().with_variant(JSONB(), 'postgresql')

# Physical DB columns requested by the RAG team. The keys are the EXACT Korean SQL names.
# Retain support_types JSON for compatibility with the frontend and existing logic.
CATEGORY_FIELD_TO_ATTR = {
    '자금': 'category_funding',
    '교육·컨설팅': 'category_education',
    '공간·시설': 'category_space',
    '홍보·판매': 'category_marketing',
    '인력': 'category_staffing',
    '기술개발': 'category_tech',
    '해외진출': 'category_export',
    '제도·인증': 'category_certification',
    '기타': 'category_other',
}


class Announcement(Base):
    __tablename__ = 'announcements'
    announcement_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(String(30), default='bizinfo', nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    agency: Mapped[str | None] = mapped_column(Text)
    operator: Mapped[str | None] = mapped_column(Text)
    category_large: Mapped[str | None] = mapped_column(String(100))
    category_medium: Mapped[str | None] = mapped_column(String(100))
    target_name: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[str | None] = mapped_column(Text)
    application_period_raw: Mapped[str | None] = mapped_column(Text)
    apply_start: Mapped[date | None] = mapped_column(Date)
    apply_end: Mapped[date | None] = mapped_column(Date)
    rolling: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    application_method: Mapped[str | None] = mapped_column(Text)
    announcement_url: Mapped[str | None] = mapped_column(Text)
    application_url: Mapped[str | None] = mapped_column(Text)
    contact: Mapped[str | None] = mapped_column(Text)
    fetched_created_at: Mapped[str | None] = mapped_column(String(30))
    fetched_updated_at: Mapped[str | None] = mapped_column(String(30))
    raw_fields: Mapped[dict] = mapped_column(FlexibleJSON, nullable=False)
    support_types: Mapped[list | None] = mapped_column(FlexibleJSON)
    # Requested human-readable CSV category label and nine physically separate 0/1 flags.
    category_display: Mapped[str | None] = mapped_column('카테고리', Text)
    category_funding: Mapped[int] = mapped_column('자금', Integer, nullable=False, default=0, server_default='0')
    category_education: Mapped[int] = mapped_column('교육·컨설팅', Integer, nullable=False, default=0, server_default='0')
    category_space: Mapped[int] = mapped_column('공간·시설', Integer, nullable=False, default=0, server_default='0')
    category_marketing: Mapped[int] = mapped_column('홍보·판매', Integer, nullable=False, default=0, server_default='0')
    category_staffing: Mapped[int] = mapped_column('인력', Integer, nullable=False, default=0, server_default='0')
    category_tech: Mapped[int] = mapped_column('기술개발', Integer, nullable=False, default=0, server_default='0')
    category_export: Mapped[int] = mapped_column('해외진출', Integer, nullable=False, default=0, server_default='0')
    category_certification: Mapped[int] = mapped_column('제도·인증', Integer, nullable=False, default=0, server_default='0')
    category_other: Mapped[int] = mapped_column('기타', Integer, nullable=False, default=0, server_default='0')
    region: Mapped[str | None] = mapped_column(String(20), index=True)
    seoul_gu: Mapped[str | None] = mapped_column(Text)
    has_text: Mapped[bool | None] = mapped_column(Boolean)
    amount_max_manwon: Mapped[int | None] = mapped_column(Integer)
    total_budget_text: Mapped[str | None] = mapped_column(Text)
    interest_rate: Mapped[str | None] = mapped_column(String(120))
    support_detail: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(30))
    duplicate_policy_json: Mapped[dict | None] = mapped_column(FlexibleJSON)
    submission_docs_json: Mapped[list | None] = mapped_column(FlexibleJSON)
    bonus_points_json: Mapped[list | None] = mapped_column(FlexibleJSON)
    rounds_json: Mapped[list | None] = mapped_column(FlexibleJSON)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime)
    files: Mapped[list['AnnouncementFile']] = relationship(back_populates='announcement', cascade='all, delete-orphan')
    texts: Mapped[list['AnnouncementText']] = relationship(back_populates='announcement', cascade='all, delete-orphan')
    condition: Mapped['Condition | None'] = relationship(back_populates='announcement', cascade='all, delete-orphan', uselist=False)


class AnnouncementFile(Base):
    __tablename__ = 'files'
    __table_args__ = (UniqueConstraint('announcement_id', 'file_role', 'sequence', name='uq_file_role_sequence'),)
    file_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    announcement_id: Mapped[str] = mapped_column(ForeignKey('announcements.announcement_id'), nullable=False, index=True)
    file_name: Mapped[str | None] = mapped_column(Text)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(16))
    file_role: Mapped[str] = mapped_column(String(30), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    download_status: Mapped[str] = mapped_column(String(32), default='not_downloaded', nullable=False)
    announcement: Mapped[Announcement] = relationship(back_populates='files')


class AnnouncementText(Base):
    __tablename__ = 'texts'
    text_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    announcement_id: Mapped[str] = mapped_column(ForeignKey('announcements.announcement_id'), nullable=False, index=True)
    content: Mapped[str | None] = mapped_column(Text)
    source_format: Mapped[str | None] = mapped_column(String(20))
    source_file_name: Mapped[str | None] = mapped_column(Text)
    extraction_status: Mapped[str] = mapped_column(String(80), default='not_attempted', nullable=False)
    suspected_incomplete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extraction_error: Mapped[str | None] = mapped_column(Text)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime)
    file_id: Mapped[int | None] = mapped_column(ForeignKey('files.file_id'))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_kind: Mapped[str | None] = mapped_column(String(30))
    section_name: Mapped[str | None] = mapped_column(String(100))
    announcement: Mapped[Announcement] = relationship(back_populates='texts')


class Condition(Base):
    __tablename__ = 'conditions'
    condition_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    announcement_id: Mapped[str] = mapped_column(ForeignKey('announcements.announcement_id'), nullable=False, unique=True)
    schema_version: Mapped[str | None] = mapped_column(String(20))
    condition_json: Mapped[dict | None] = mapped_column(FlexibleJSON)
    sido: Mapped[str | None] = mapped_column(String(70), index=True)
    business_registration: Mapped[str | None] = mapped_column(String(60), index=True)
    max_startup_months: Mapped[int | None] = mapped_column(Integer, index=True)
    max_age: Mapped[int | None] = mapped_column(Integer, index=True)
    extraction_status: Mapped[str] = mapped_column(String(30), default='not_extracted', nullable=False)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_text_id: Mapped[int | None] = mapped_column(ForeignKey('texts.text_id'))
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    quote_validation_status: Mapped[str | None] = mapped_column(String(30))
    announcement: Mapped[Announcement] = relationship(back_populates='condition')
