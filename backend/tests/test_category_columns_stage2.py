"""Requested physical SQL columns, OR semantics, and strict teammate CSV agreement."""
from pathlib import Path
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Announcement, CATEGORY_FIELD_TO_ATTR
from app.main import list_announcements
from scripts.import_mappings import load_map


def make_session():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    return engine,Session(engine)


def test_physical_korean_flag_columns_and_defaults():
    cols=Announcement.__table__.columns
    assert {'region','seoul_gu','has_text','카테고리',*CATEGORY_FIELD_TO_ATTR}.issubset(cols.keys())
    engine,session=make_session()
    with session:
        session.add(Announcement(announcement_id='A',title='test',raw_fields={},support_types=['자금']))
        session.commit()
        row=session.get(Announcement,'A')
        assert row.category_funding == 0   # flags intentionally independent until CSV import or migration
    engine.dispose()


def test_multi_category_or_sql_filter_and_response_flags():
    engine,session=make_session()
    with session:
        records=[('A',1,0),('B',0,1),('C',1,1),('D',0,0)]
        for aid,funding,space in records:
            a=Announcement(announcement_id=aid,title='sample',raw_fields={},
                           category_display=', '.join(name for name,v in [('자금',funding),('공간·시설',space)] if v),
                           category_funding=funding,category_space=space,
                           support_types=[name for name,v in [('자금',funding),('공간·시설',space)] if v])
            session.add(a)
        session.commit()
        res=list_announcements(q=None,category='자금',limit=20,offset=0,session=session)
        assert res.total==2
        res=list_announcements(q=None,category='자금,공간·시설',limit=20,offset=0,session=session)
        assert res.total==3  # OR, not AND or double count
        assert res.items[0].category_label is not None
        assert len(res.items[0].category_flags)==9
        assert res.items[0].category_flags['자금'] in (0,1)
        with pytest.raises(HTTPException) as error:
            list_announcements(q=None,category='비허용카테고리',limit=20,offset=0,session=session)
        assert error.value.status_code==422
    engine.dispose()


def test_teammate_0_1_values_are_validated(tmp_path):
    names=','.join(CATEGORY_FIELD_TO_ATTR)
    row='1,0,1,0,0,0,0,0,0'
    path=tmp_path/'cat.csv'
    path.write_text('pblancId,카테고리,'+names+'\nA,"자금, 공간·시설",'+row+'\n',encoding='utf-8-sig')
    assert load_map(path,'category')['A']==['자금','공간·시설']
    path.write_text('pblancId,카테고리,'+names+'\nA,"자금, 공간·시설",0,0,1,0,0,0,0,0,0\n',encoding='utf-8-sig')
    with pytest.raises(ValueError,match='불일치'):
        load_map(path,'category')
