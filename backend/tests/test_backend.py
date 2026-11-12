import json
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app, get_session
from app.db import Base
from app.models import Announcement, AnnouncementFile, AnnouncementText, Condition
from app.condition_utils import projection, validate_condition
from scripts.ingest import file_pairs, parse_period, rows_to_announcements
import pytest

@pytest.fixture()
def client():
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    @event.listens_for(engine, 'connect')
    def fk(dbapi_connection, _):
        dbapi_connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        a = Announcement(announcement_id='PBLN_TEST', title='테스트 지원사업', raw_fields={'pblancNm':'테스트 지원사업'}, rolling=False)
        s.add(a)
        s.add(AnnouncementText(announcement_id='PBLN_TEST', extraction_status='추출실패', content=None))
        s.add(Condition(announcement_id='PBLN_TEST', extraction_status='not_extracted', condition_json=None))
        s.commit()
    def override():
        with Session(engine) as s:
            yield s
    app.dependency_overrides[get_session] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_health(client):
    assert client.get('/health').json()['status'] == 'ok'


def test_list_detail_text_and_conditions(client):
    r=client.get('/api/v1/announcements')
    assert r.status_code==200 and r.json()['total']==1
    ann=client.get('/api/v1/announcements/PBLN_TEST').json()
    assert ann['title']=='테스트 지원사업' and ann['fields']['pblancNm']=='테스트 지원사업'
    assert client.get('/api/v1/announcements/PBLN_TEST/text').json()['content'] is None
    cond=client.get('/api/v1/announcements/PBLN_TEST/conditions').json()
    assert cond['extraction_status']=='not_extracted' and cond['condition_json'] is None
    assert client.get('/api/v1/announcements/NOT_FOUND').status_code==404


def test_local_demo_returns_frontend_contract_without_fake_eligibility(client):
    r = client.post('/api/support-match', json={'text':'서울에 사는 27세 예비창업자이며 카페 창업 지원을 찾습니다'})
    assert r.status_code==200
    body=r.json()
    assert body['meta']['dataSource']=='mock' and body['meta']['parser']=='rule'
    assert all(x['verdict']=='확인 필요' for x in body['results'])
    assert body['summary']['eligibleCount']==0
    assert body['conditional']==[] and body['excluded']==[]
    assert body['profile']['age']['value']==27
    assert body['profile']['sido']['value']=='서울특별시'
    assert set(['profile','missing','results','conditional','excluded','nextSteps','summary','coverage','meta']).issubset(body)
    assert client.post('/api/support-match',json={'text':''}).status_code==422


def test_file_separator_and_date():
    files=list(file_pairs({'printFileNm':'one.pdf','printFlpthNm':'https://x/1','fileNm':'a.hwp@b.pdf','flpthNm':'https://x/2@https://x/3'}))
    assert len(files)==3 and files[-1][2]=='b.pdf'
    assert parse_period('2026-10-12 ~ 2026-10-23')==(date(2026,10,12),date(2026,10,23),False)
    assert parse_period('예산 소진시까지')==(None,None,True)


def test_projection_conservative():
    data={'지역':{'상태':'있음','범위':[{'시도':'서울특별시','권역':None,'시군구':None}]},'나이':{'상태':'있음','max':39,'대상':'대표자'},'업력':{'상태':'있음','max_개월':36},'사업자등록':{'상태':'있음','값':'필수'},'대안조건':[],'트랙':[]}
    assert projection(data)=={'sido':'서울특별시','business_registration':'필수','max_startup_months':36,'max_age':39}
    data['트랙']=[{'이름':'예비창업'}]
    assert all(v is None for v in projection(data).values())


def test_idempotent_ingest_and_foreign_keys():
    engine=create_engine('sqlite://',poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def fk(conn,_):conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    row={'pblancId':'PBLN_A','pblancNm':'테스트','printFileNm':'test.hwp','printFlpthNm':'https://example.com/1','fileNm':'','flpthNm':'','reqstBeginEndDe':'상시 접수'}
    with Session(engine) as s:
        rows_to_announcements(s,[row]);s.commit()
        rows_to_announcements(s,[row]);s.commit()
        assert s.scalar(select(func.count()).select_from(Announcement))==1
        assert s.scalar(select(func.count()).select_from(AnnouncementFile))==1
        assert s.scalar(select(func.count()).select_from(Condition))==1
        assert s.get(Announcement,'PBLN_A').raw_fields['pblancId']=='PBLN_A'
    engine.dispose()
