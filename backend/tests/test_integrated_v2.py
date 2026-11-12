from datetime import date
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db import Base, get_session
from app.models import Announcement, AnnouncementText, Condition
from app.extended_models import UserRequest, MatchRun, MatchResult, ConditionCheck
from app.main import app


def test_integrated_8_tables_and_relationships():
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def foreign_keys(dbapi,_):dbapi.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    assert {'announcements','files','texts','conditions','user_requests','match_runs','match_results','condition_checks'}.issubset(Base.metadata.tables)
    with Session(engine) as session:
        session.add(Announcement(announcement_id='PBLN_TWO',title='서울 예비창업 지원사업',raw_fields={},apply_start=date(2026,10,1),apply_end=date(2026,11,30),rolling=False))
        session.flush()
        session.add_all([AnnouncementText(announcement_id='PBLN_TWO',content='대표 원문',source_kind='attachment',extraction_status='success',is_primary=True),
                         AnnouncementText(announcement_id='PBLN_TWO',content='추가 원문',source_kind='attachment',extraction_status='success',is_primary=False)])
        session.add(Condition(announcement_id='PBLN_TWO',extraction_status='not_extracted'))
        session.flush()
        u=UserRequest(input_text='서울 예비창업을 희망합니다',profile_json={'sido':'서울특별시'})
        session.add(u);session.flush()
        run=MatchRun(request_id=u.request_id,execution_status='success',data_source='local_demo',search_version='keyword_v1')
        session.add(run);session.flush()
        r=MatchResult(run_id=run.run_id,announcement_id='PBLN_TWO',verdict='확인 필요',verdict_source='demo_unverified',score=31)
        session.add(r);session.flush()
        session.add(ConditionCheck(result_id=r.result_id,check_status='unknown',reason='AI 조건 미추출'))
        session.commit()
        assert session.scalar(select(func.count()).select_from(AnnouncementText))==2
        assert session.scalar(select(func.count()).select_from(ConditionCheck))==1
    engine.dispose()

def test_real_demo_contract(client=None):
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def foreign_keys(dbapi,_):dbapi.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Announcement(announcement_id='PBLN_ONE',title='서울 청년 예비창업자 교육 지원',summary='사업화 교육 과정',rolling=False,apply_start=date(2026,10,1),apply_end=date(2026,11,30),raw_fields={'trgetNm':'청년 예비창업자'}))
        s.commit()
    def override():
        with Session(engine) as s:yield s
    app.dependency_overrides[get_session]=override
    try:
        r=TestClient(app).post('/api/support-match',json={'text':'서울에 거주하는 29세 예비창업자로 창업 교육을 찾고 있어요.'})
        assert r.status_code==200
        d=r.json()
        assert d['results'] and d['results'][0]['program']['title']=='서울 청년 예비창업자 교육 지원'
        assert d['results'][0]['verdict']=='확인 필요'
        assert d['results'][0]['rules']==[] and d['results'][0]['reasons']==[]
        assert d['summary']['eligibleCount']==0
        assert d['meta']['dataSource']=='mock' and d['coverage']['total']==1
        assert d['results'][0]['program']['source']=='bizinfo'
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
