"""DB-backed FastAPI, schema-v0.4 user extractor, frontend-compatible conservative search."""
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
from fastapi import Depends, FastAPI, HTTPException, Query, status
import json
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, text as sql_text, or_
from sqlalchemy.orm import Session, selectinload
from app.db import get_session
from app.models import Announcement, AnnouncementFile, AnnouncementText, Condition, CATEGORY_FIELD_TO_ATTR
from app import extended_models  # register integrated ERD models
from app.schemas import AnnouncementListResponse, AnnouncementSummary, AnnouncementDetail, AttachmentResponse, ConditionResponse, TextResponse, SupportMatchRequest, ApiError

app = FastAPI(title='Startup Support Backend API', version='0.1.0', description='공고 및 AI 산출물 데이터 조회용 FastAPI 초안. AI 판정 미연동.')
# Vite's local dev server. Explicit origins, not wildcard with credentials.
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_credentials=False, allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


def summary(a: Announcement, text_status=None, cond_status=None):
    return AnnouncementSummary(announcement_id=a.announcement_id, title=a.title, agency=a.agency, support_types=a.support_types or [], category_label=a.category_display, category_flags={name: getattr(a, attr) for name,attr in CATEGORY_FIELD_TO_ATTR.items()}, region=a.region, seoul_gu=a.seoul_gu, has_text=a.has_text, category_large=a.category_large, category_medium=a.category_medium, target_name=a.target_name, summary=a.summary, application_period_raw=a.application_period_raw, apply_start=a.apply_start, apply_end=a.apply_end, rolling=a.rolling, announcement_url=a.announcement_url, text_extraction_status=text_status, condition_extraction_status=cond_status)


@app.get('/health')
def health(session: Session = Depends(get_session)):
    try:
        session.execute(sql_text('SELECT 1'))
        return {'status': 'ok', 'database': 'connected'}
    except Exception:
        raise HTTPException(503, detail='DB 연결 실패')


@app.get('/api/v1/announcements', response_model=AnnouncementListResponse)
def list_announcements(q: str | None = Query(None, min_length=1), category: str | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), session: Session = Depends(get_session)):
    stmt = select(Announcement)
    if q:
        stmt = stmt.where(Announcement.title.ilike(f'%{q}%'))
    if category:
        # Single category or comma-separated multi-select (OR) from the *physical* 0/1 columns.
        # This is distinct from category_large (the raw Bizinfo top-level category).
        requested = list(dict.fromkeys(x.strip() for x in category.split(',') if x.strip()))
        invalid = [x for x in requested if x not in CATEGORY_FIELD_TO_ATTR]
        if invalid:
            raise HTTPException(422, detail=f'지원 카테고리 오류: {invalid}')
        if requested:
            stmt = stmt.where(or_(*(getattr(Announcement, CATEGORY_FIELD_TO_ATTR[name]) == 1 for name in requested)))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    announcements = session.scalars(stmt.order_by(Announcement.announcement_id.desc()).offset(offset).limit(limit)).all()
    ids = [a.announcement_id for a in announcements]
    tstat = dict(session.execute(select(AnnouncementText.announcement_id, AnnouncementText.extraction_status).where(AnnouncementText.announcement_id.in_(ids))).all()) if ids else {}
    cstat = dict(session.execute(select(Condition.announcement_id, Condition.extraction_status).where(Condition.announcement_id.in_(ids))).all()) if ids else {}
    return AnnouncementListResponse(items=[summary(a, tstat.get(a.announcement_id), cstat.get(a.announcement_id)) for a in announcements], total=total, limit=limit, offset=offset)


def found(session: Session, announcement_id: str) -> Announcement:
    a = session.get(Announcement, announcement_id)
    if not a:
        raise HTTPException(404, detail='해당 공고 ID가 없습니다')
    return a


@app.get('/api/v1/announcements/{announcement_id}', response_model=AnnouncementDetail)
def get_announcement(announcement_id: str, session: Session = Depends(get_session)):
    a = session.scalar(select(Announcement).where(Announcement.announcement_id == announcement_id).options(selectinload(Announcement.files)))
    if a is None:
        raise HTTPException(404, detail='해당 공고 ID가 없습니다')
    base = summary(a)
    t = session.scalar(select(AnnouncementText).where(AnnouncementText.announcement_id == announcement_id).order_by(AnnouncementText.is_primary.desc(), AnnouncementText.text_id.asc()))
    c = session.scalar(select(Condition).where(Condition.announcement_id == announcement_id))
    return AnnouncementDetail(**{**base.model_dump(), 'text_extraction_status': t.extraction_status if t else None, 'condition_extraction_status': c.extraction_status if c else None, 'operator': a.operator, 'application_method': a.application_method, 'application_url': a.application_url, 'contact': a.contact, 'hashtags': a.hashtags, 'fields': {k: str(v) for k,v in a.raw_fields.items() if isinstance(v,str)}, 'files': [AttachmentResponse(file_id=f.file_id, file_name=f.file_name, file_url=f.file_url, file_type=f.file_type, file_role=f.file_role, download_status=f.download_status) for f in sorted(a.files, key=lambda f: (f.file_role,f.sequence))]})


@app.get('/api/v1/announcements/{announcement_id}/conditions', response_model=ConditionResponse)
def get_condition(announcement_id: str, session: Session = Depends(get_session)):
    found(session, announcement_id)
    obj = session.scalar(select(Condition).where(Condition.announcement_id == announcement_id))
    if obj is None:
        return ConditionResponse(announcement_id=announcement_id, extraction_status='not_extracted', schema_version=None, condition_json=None, sido=None, business_registration=None, max_startup_months=None, max_age=None)
    return ConditionResponse(announcement_id=announcement_id, extraction_status=obj.extraction_status, schema_version=obj.schema_version, condition_json=obj.condition_json, sido=obj.sido, business_registration=obj.business_registration, max_startup_months=obj.max_startup_months, max_age=obj.max_age)


@app.get('/api/v1/announcements/{announcement_id}/text', response_model=TextResponse)
def get_text(announcement_id: str, session: Session = Depends(get_session)):
    found(session, announcement_id)
    t = session.scalar(select(AnnouncementText).where(AnnouncementText.announcement_id == announcement_id).order_by(AnnouncementText.is_primary.desc(), AnnouncementText.text_id.asc()))
    return TextResponse(announcement_id=announcement_id, extraction_status=t.extraction_status if t else 'not_attempted', source_format=t.source_format if t else None, suspected_incomplete=t.suspected_incomplete if t else False, content=t.content if t else None, extraction_error=t.extraction_error if t else None)


from app.local_demo import get_match_response

@app.post('/api/support-match', summary='로컬 DB 기반 규칙 검색 데모 (실제 자격 판정 아님)')
def support_match(request: SupportMatchRequest, session: Session = Depends(get_session)):
    """Same frontend POST contract. AI extraction opt-in; no unverified eligibility claims."""
    import os
    from user_extraction import extract_user_info
    from user_extraction.demo_rules import demo_extract
    mode = os.getenv('AI_MATCH_MODE','off').strip().lower()
    extracted = None
    if mode == 'demo':
        extracted = demo_extract(request.text)
    elif mode == 'llm':
        if not os.getenv('OPENAI_API_KEY'):
            raise HTTPException(503, detail='AI_MATCH_MODE=llm 이지만 OPENAI_API_KEY가 없습니다')
        if os.getenv('RENDER') and os.getenv('ENABLE_PUBLIC_LLM','false').lower() != 'true':
            raise HTTPException(503, detail='공개 LLM 호출은 기본 비활성화입니다. 보안/사용량 제한 설정 후 활성화하세요.')
        try:
            extracted = extract_user_info(request.text)
        except Exception as exc:
            raise HTTPException(502, detail=f'사용자 정보 AI 추출 실패: {type(exc).__name__}') from exc
    elif mode != 'off':
        raise HTTPException(500, detail='AI_MATCH_MODE는 off / demo / llm만 가능합니다')
    payload = get_match_response(request, session, extracted=extracted)

    from app.local_run_store import maybe_save_demo_run
    maybe_save_demo_run(session, payload)  # opt-in only; user prompts are private by default
    return payload


from typing import Literal
from pydantic import BaseModel, Field

class UserExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    mode: Literal['demo','llm'] = 'llm'
    user_id: str | None = None

@app.post('/api/v1/user-extract', summary='사용자 자연어 추출 (Schema v0.4)')
def user_extract(payload: UserExtractRequest):
    """Separate API for integration and testing. Does not persist user utterances."""
    import os
    from user_extraction import extract_user_info
    from user_extraction.demo_rules import demo_extract
    if payload.mode == 'demo':
        return {'mode':'demo','is_real_llm':False,'result':demo_extract(payload.text,user_id=payload.user_id)}
    if os.getenv('RENDER') and os.getenv('ENABLE_PUBLIC_LLM','false').lower() != 'true':
        raise HTTPException(503, detail='공개 LLM 기능은 비활성화입니다. 개인 테스트 후 보안/비용 제한 정책을 설정하세요.')
    if not os.getenv('OPENAI_API_KEY'):
        raise HTTPException(503, detail='OPENAI_API_KEY가 필요합니다. .env 설정을 확인하세요.')
    try:
        return {'mode':'llm','is_real_llm':True,'result':extract_user_info(payload.text,user_id=payload.user_id)}
    except Exception as exc:
        raise HTTPException(502, detail=f'LLM 추출 실패: {type(exc).__name__}') from exc
