"""Contracts needed by the October 27 frontend revision."""
from datetime import date
from pathlib import Path
import re
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Announcement
from app.local_demo import get_match_response, get_profile
from app.schemas import SupportMatchRequest


FRONTEND = Path(__file__).resolve().parents[2] / 'frontend'
CATEGORIES = ['자금', '교육·컨설팅', '공간·시설', '홍보·판매', '인력', '기술개발', '해외진출', '제도·인증', '기타']


def test_latest_frontend_categories_match_local_api():
    if not FRONTEND.is_dir(): pytest.skip("backend-only package: frontend owned by teammate")
    types = (FRONTEND/'src/services/supportMatch/types.ts').read_text(encoding='utf-8')
    assert all(f"'{name}'" in types for name in CATEGORIES)
    assert len(CATEGORIES) == 9
    results = (FRONTEND/'src/pages/SupportMatchResults.tsx').read_text(encoding='utf-8')
    assert '(r.program.support_types ?? []).some' in results


def test_latest_frontend_city_district_override_is_supported():
    profile, missing = get_profile('29살 서울 마포구 카페 예비창업', {
        'age': 45, 'sido': '서울특별시', 'sigungu': '종로구',
        'bizStage': '기창업', 'industryCategory': '카페',
    })
    assert profile['age']['value'] == 45
    assert profile['sido']['value'] == '서울특별시'
    assert profile['sigungu']['value'] == '종로구'
    assert profile['bizStage']['value'] == '기창업'
    assert '청년' not in profile['targetGroups']
    assert 'age' not in missing and 'sido' not in missing


def test_latest_frontend_unknown_values_remain_null():
    profile, missing = get_profile('사업 정보를 찾고 있습니다', None)
    assert profile['age']['value'] is None
    assert profile['sido']['value'] is None
    assert 'age' in missing


def test_latest_frontend_9_categories_and_mock_status():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Announcement(
            announcement_id='PBLN_DEMO', title='서울 카페 창업지원 교육', raw_fields={},
            region='전국', support_types=['자금', '교육·컨설팅'],
            apply_start=date(2026, 10, 1), apply_end=date(2026, 12, 31),
        ))
        session.commit()
        res = get_match_response(SupportMatchRequest(text='29살 서울 카페 창업 교육'), session, as_of=date(2026, 10, 28))
        assert res['meta']['dataSource'] == 'mock'
        assert res['results']
        r = res['results'][0]
        assert r['program']['support_types'] == ['자금', '교육·컨설팅']
        assert r['verdict'] == '확인 필요' and r['judgmentScore'] is None
        assert all(k in res for k in ('profile','missing','meta','summary','results','conditional','excluded','nextSteps'))
    engine.dispose()


def test_latest_frontend_source_preserved_and_backend_hosts_build():
    if not FRONTEND.is_dir(): pytest.skip("backend-only package: frontend owned by teammate")
    # The original frontend configuration is intentionally unchanged.
    vite = (FRONTEND/'vite.config.ts').read_text(encoding='utf-8')
    assert 'server: { proxy:' in vite  # commented out in the original frontend
    assert "target: 'http://127.0.0.1:8000'" not in vite
    client = (FRONTEND/'src/services/supportMatch/client.ts').read_text(encoding='utf-8')
    assert "fetch('/api/support-match'" in client
    assert 'return buildUiPlaceholder' in client  # original fallback behavior retained
    import app.fullstack as fullstack
    assert fullstack.DIST == FRONTEND / 'dist'
    assert any(getattr(r, 'path', '') == '/{frontend_path:path}' for r in fullstack.app.routes)
