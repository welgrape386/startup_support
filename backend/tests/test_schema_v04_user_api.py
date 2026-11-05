import os
from fastapi.testclient import TestClient
from app.main import app
from app.models import CATEGORY_FIELD_TO_ATTR
from user_extraction.demo_rules import demo_extract

def test_schema_v04_user_extract_endpoint():
    c=TestClient(app)
    r=c.post('/api/v1/user-extract',json={'text':'마포구에서 디저트 카페를 준비하는 예비창업자예요. 라이브커머스를 하고 싶어요.','mode':'demo'})
    assert r.status_code==200, r.text
    obj=r.json()
    assert obj['is_real_llm'] is False
    assert obj['result']['검색정보']['검색지역']=='마포구'
    assert '홍보·판매' in obj['result']['검색정보']['필요지원']
    assert obj['result']['사용자프로필']['사업자이력'] is None

def test_no_api_key_should_not_fallback_to_demo(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    r=TestClient(app).post('/api/v1/user-extract',json={'text':'카페를 하고 싶어요','mode':'llm'})
    assert r.status_code ==503

def test_all_nine_flags_in_orm():
    from app.models import Announcement
    for name,attr in CATEGORY_FIELD_TO_ATTR.items():
        assert getattr(Announcement,attr).property.columns[0].name == name

def test_user_profile_missing_registered_is_null():
    data=demo_extract('크라우드펀딩으로 창업 자금을 모아보고 싶어요.')
    assert data['사용자프로필']['사업자이력'] is None
