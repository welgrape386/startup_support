#!/usr/bin/env python3
"""
SQLite → Supabase(PostgreSQL) 마이그레이션 스크립트.

사용법:
    DATABASE_URL="postgresql://..." python scripts/migrate_sqlite_to_supabase.py

환경변수 DATABASE_URL이 없으면 .env에서 읽습니다.
"""
import os
import sys
import json
from pathlib import Path

# .env 로드
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)

DATABASE_URL = os.getenv('DATABASE_URL', '')
if not DATABASE_URL or DATABASE_URL.startswith('sqlite:'):
    print('ERROR: DATABASE_URL에 Supabase PostgreSQL URI를 설정하세요.')
    print('  예) DATABASE_URL="postgresql://postgres.[ref]:[password]@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres"')
    sys.exit(1)

SQLITE_PATH = Path(__file__).resolve().parents[1] / 'data' / 'startup_support.db'
if not SQLITE_PATH.exists():
    print(f'ERROR: SQLite DB 파일을 찾을 수 없어요: {SQLITE_PATH}')
    sys.exit(1)

print(f'SQLite: {SQLITE_PATH}')
print(f'Target: {DATABASE_URL[:60]}...')
print()

# psycopg / SQLAlchemy 준비
try:
    import psycopg
except ImportError:
    print('psycopg 설치 중...')
    os.system(f'{sys.executable} -m pip install -q psycopg[binary] --break-system-packages')
    import psycopg

import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

# --- SQLite 연결 ---
sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
sqlite_conn.row_factory = sqlite3.Row

# --- PostgreSQL 연결 (psycopg 직접) ---
pg_dsn = DATABASE_URL
if pg_dsn.startswith('postgresql+psycopg://'):
    pg_dsn = pg_dsn.replace('postgresql+psycopg://', 'postgresql://', 1)

# SQLAlchemy engine (테이블 생성용)
pg_url_sa = DATABASE_URL
if pg_url_sa.startswith('postgresql://'):
    pg_url_sa = pg_url_sa.replace('postgresql://', 'postgresql+psycopg://', 1)
elif pg_url_sa.startswith('postgres://'):
    pg_url_sa = pg_url_sa.replace('postgres://', 'postgresql+psycopg://', 1)

pg_engine = create_engine(pg_url_sa, pool_pre_ping=True)

# --- 테이블 스키마 생성 (이미 존재하면 스킵) ---
print('1) PostgreSQL에 테이블 생성 중...')

# 테이블이 이미 있는지 psycopg로 직접 확인 후 없을 때만 생성
with psycopg.connect(pg_dsn, prepare_threshold=None) as _chk:
    with _chk.cursor() as _cur:
        _cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='announcements'"
        )
        _has_tables = (_cur.fetchone()[0] or 0) > 0

if not _has_tables:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ['DATABASE_URL'] = DATABASE_URL
    from app.models import Base as ModelBase
    from app import extended_models
    ModelBase.metadata.create_all(pg_engine)
    from app.extended_models import Base as ExtBase
    ExtBase.metadata.create_all(pg_engine)
    print('   테이블 생성 완료')
else:
    print('   테이블 이미 존재 — 스킵')

# --- PostgreSQL boolean 컬럼 목록 조회 ---
def get_pg_bool_columns(table: str) -> set:
    """PostgreSQL에서 boolean 타입인 컬럼 이름 집합 반환"""
    try:
        with pg_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :tbl AND data_type = 'boolean'"
            ), {'tbl': table})
            return {row[0] for row in result}
    except Exception:
        return set()

# --- 데이터 복사 ---
TABLES_IN_ORDER = [
    'announcements',
    'files',
    'texts',
    'conditions',
    'user_requests',
    'match_runs',
    'match_results',
    'condition_checks',
]

def get_sqlite_rows(table: str):
    cur = sqlite_conn.execute(f'SELECT * FROM "{table}"')
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return cols, [dict(zip(cols, row)) for row in rows]


def upsert_rows(table: str, cols: list, rows: list):
    if not rows:
        print(f'   {table}: 0행 (스킵)')
        return

    # PostgreSQL의 boolean 컬럼 파악
    bool_cols = get_pg_bool_columns(table)

    # PK 컬럼 찾기 (SQLite PRAGMA)
    pk_info = sqlite_conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    pk_cols = [row[1] for row in pk_info if row[5] > 0]

    # psycopg 직접 연결로 upsert (% 바인딩 사용 — psycopg 네이티브)
    # prepare=False: Transaction pooler는 prepared statement 미지원
    with psycopg.connect(pg_dsn, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            col_str = ', '.join(f'"{c}"' for c in cols)
            placeholders = ', '.join(['%s'] * len(cols))

            if pk_cols:
                pk_str = ', '.join(f'"{c}"' for c in pk_cols)
                update_str = ', '.join(
                    f'"{c}" = EXCLUDED."{c}"'
                    for c in cols if c not in pk_cols
                )
                sql = (
                    f'INSERT INTO "{table}" ({col_str}) VALUES ({placeholders}) '
                    f'ON CONFLICT ({pk_str}) DO UPDATE SET {update_str}'
                )
            else:
                sql = f'INSERT INTO "{table}" ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

            # 값 변환: bytes → str, boolean 컬럼 smallint → bool
            cleaned = []
            for row in rows:
                r = []
                for c in cols:
                    v = row[c]
                    if isinstance(v, bytes):
                        v = v.decode('utf-8', errors='replace')
                    if c in bool_cols and isinstance(v, int):
                        v = bool(v)
                    r.append(v)
                cleaned.append(r)

            cur.executemany(sql, cleaned)
        conn.commit()

    print(f'   {table}: {len(rows)}행 완료')


print('2) 데이터 복사 중...')
for table in TABLES_IN_ORDER:
    exists = sqlite_conn.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
    ).fetchone()
    if not exists:
        print(f'   {table}: SQLite에 없음 (스킵)')
        continue

    cols, rows = get_sqlite_rows(table)
    upsert_rows(table, cols, rows)

# alembic_version도 복사
try:
    cols, rows = get_sqlite_rows('alembic_version')
    upsert_rows('alembic_version', cols, rows)
except Exception:
    pass

sqlite_conn.close()
print()
print('마이그레이션 완료!')
print('Render 환경변수 DATABASE_URL을 같은 값으로 설정하면 바로 연결됩니다.')
