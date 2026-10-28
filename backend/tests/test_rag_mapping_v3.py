from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Announcement
from app.extended_models import UserRequest, MatchResult
from app.local_demo import get_match_response
from app.schemas import SupportMatchRequest
from scripts.import_mappings import load_map


def test_v3_columns_are_nullable_and_data_types():
    engine=create_engine('sqlite://',poolclass=StaticPool, connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Announcement(announcement_id='X', title='테스트', raw_fields={}))
        s.add(UserRequest(input_text='나이에 대해 말하지 않았어요', age=None, gender=None, startup_months=None, is_registered=None))
        s.commit()
        u=s.query(UserRequest).one()
        assert u.age is None and u.gender is None and u.startup_months is None and u.is_registered is None
    assert {'region','seoul_gu','has_text'}.issubset(Announcement.__table__.columns.keys())
    assert {'search_score','judgment_score'}.issubset(MatchResult.__table__.columns.keys())
    engine.dispose()


def test_region_filter_gu_and_separate_scores():
    engine=create_engine('sqlite://',poolclass=StaticPool, connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        for aid, reg, gu in [('S','서울','마포구'),('J','서울','종로구'),('N','전국',None),('O','타지역',None)]:
            s.add(Announcement(announcement_id=aid,title=f'{aid} 서울 카페 교육',raw_fields={},region=reg,seoul_gu=gu,
                               apply_start=date(2026,10,1),apply_end=date(2026,12,1)))
        s.commit()
        payload=get_match_response(SupportMatchRequest(text='서울 마포구 거주 29살이고 카페 교육 찾습니다'),s,as_of=date(2026,10,28))
        ids={r['program']['id'] for r in payload['results']}
        assert ids=={'S','N'}
        assert all('searchScore' in r and r['judgmentScore'] is None and r['verdict']=='확인 필요' for r in payload['results'])
    engine.dispose()


def test_map_parser_validates_exact_labels(tmp_path):
    region=tmp_path/'region.csv'
    region.write_text('pblancId,region,seoul_gu,has_text\nA,서울,"마포구,서대문구",0\nB,전국,,1\n',encoding='utf-8-sig')
    got=load_map(region,'region')
    assert got['A']=={'region':'서울','seoul_gu':'마포구,서대문구','has_text':False}
    cat=tmp_path/'category.csv'
    cat.write_text('pblancId,카테고리\nA,"자금, 공간·시설"\nB,기타\n',encoding='utf-8-sig')
    assert load_map(cat,'category')['A']==['자금','공간·시설']
    cat.write_text('pblancId,카테고리\nA,사업화\n',encoding='utf-8-sig')
    with pytest.raises(ValueError,match='미등록 카테고리'):
        load_map(cat,'category')
