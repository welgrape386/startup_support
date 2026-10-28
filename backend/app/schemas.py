"""Documented read-only API shapes. POST match preserves the frontend request contract."""
from datetime import date
from typing import Any
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str
    database: str

class AnnouncementSummary(BaseModel):
    announcement_id: str
    title: str
    agency: str | None
    support_types: list[str] = Field(default_factory=list)
    category_label: str | None = None
    category_flags: dict[str, int] = Field(default_factory=dict)
    region: str | None = None
    seoul_gu: str | None = None
    has_text: bool | None = None
    category_large: str | None
    category_medium: str | None
    target_name: str | None
    summary: str | None
    application_period_raw: str | None
    apply_start: date | None
    apply_end: date | None
    rolling: bool
    announcement_url: str | None
    text_extraction_status: str | None
    condition_extraction_status: str | None

class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementSummary]
    total: int
    limit: int
    offset: int

class AttachmentResponse(BaseModel):
    file_id: int
    file_name: str | None
    file_url: str
    file_type: str | None
    file_role: str
    download_status: str

class AnnouncementDetail(AnnouncementSummary):
    operator: str | None
    application_method: str | None
    application_url: str | None
    contact: str | None
    hashtags: str | None
    files: list[AttachmentResponse]
    fields: dict[str, str]

class ConditionResponse(BaseModel):
    announcement_id: str
    extraction_status: str
    schema_version: str | None
    condition_json: dict | None
    sido: str | None
    business_registration: str | None
    max_startup_months: int | None
    max_age: int | None

class TextResponse(BaseModel):
    announcement_id: str
    extraction_status: str
    source_format: str | None
    suspected_incomplete: bool
    content: str | None
    extraction_error: str | None

class SupportMatchRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    overrides: dict[str, Any] | None = None

class ApiErrorDetail(BaseModel):
    code: str
    message: str

class ApiError(BaseModel):
    error: ApiErrorDetail
