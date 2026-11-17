"""SQLite → Supabase(PostgreSQL) 데이터 이전 스크립트.
사용법: backend/ 폴더에서
  PYTHONPATH=. python scripts/migrate_to_supabase.py
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from dotenv import load_dotenv

# .env 로드 (DATABASE_URL = Supabase)
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

SQLITE_URL = 'sqlite:///./data/startup_support.db'
PG_URL = os.environ['DATABASE_URL']

if 'sqlite' in PG_URL:
    print('❌ DATABASE_URL이 SQLite입니다. .env에 Supabase URL을 설정하세요.')
    sys.exit(1)

if PG_URL.startswith('postgresql://'):
    PG_URL = PG_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
elif PG_URL.startswith('postgres://'):
    PG_URL = PG_URL.replace('postgres://', 'postgresql+psycopg://', 1)

sqlite_engine = sa.create_engine(SQLITE_URL, connect_args={'check_same_thread': False})
pg_engine     = sa.create_engine(PG_URL, pool_pre_ping=True)

SQLiteSession = sessionmaker(bind=sqlite_engine)
PGSession     = sessionmaker(bind=pg_engine)

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

def get_rows(conn, table: str):
    result = conn.execute(sa.text(f'SELECT * FROM "{table}"'))
    cols = list(result.keys())
    return cols, [dict(zip(cols, row)) for row in result]

def pg_col_names(pg_conn, table: str):
    res = pg_conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_schema='public' AND table_name='{table}' ORDER BY ordinal_position"
    ))
    return {r[0] for r in res}

def migrate_table(sqlite_conn, pg_conn, table: str):
    cols, rows = get_rows(sqlite_conn, table)
    if not rows:
        print(f'  {table}: 0건 (건너뜀)')
        return

    pg_cols = pg_col_names(pg_conn, table)

    # Supabase에 없는 컬럼 제외
    valid_cols = [c for c in cols if c in pg_cols]
    skipped = [c for c in cols if c not in pg_cols]
    if skipped:
        print(f'  {table}: 컬럼 제외 {skipped}')

    # JSON 필드 직렬화 (SQLite는 문자열로 저장된 경우 있음)
    def fix_row(row):
        fixed = {}
        for c in valid_cols:
            v = row[c]
            if isinstance(v, str):
                stripped = v.strip()
                if stripped and stripped[0] in ('{', '['):
                    try:
                        v = json.loads(v)
                    except Exception:
                        pass
            fixed[c] = v
        return fixed

    cleaned = [fix_row(r) for r in rows]

    # 기존 데이터 삭제 후 삽입 (idempotent)
    pg_conn.execute(sa.text(f'DELETE FROM "{table}"'))

    # 컬럼명에 한글·특수문자 포함 가능 → sa.text()의 :param 방식 대신
    # psycopg3 execute_many 방식으로 삽입 (% 포맷 사용)
    col_list = ', '.join(f'"{c}"' for c in valid_cols)
    # psycopg3은 %s 플레이스홀더 사용
    placeholders = ', '.join(['%s'] * len(valid_cols))
    raw_sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'

    BATCH = 100
    raw_conn = pg_conn.connection.dbapi_connection
    with raw_conn.cursor() as cur:
        for i in range(0, len(cleaned), BATCH):
            batch = cleaned[i:i+BATCH]
            values = [[row[c] for c in valid_cols] for row in batch]
            cur.executemany(raw_sql, values)

    print(f'  {table}: {len(cleaned)}건 이전 완료')

def main():
    print('=== SQLite → Supabase 데이터 이전 시작 ===')
    with sqlite_engine.connect() as sc, pg_engine.connect() as pc:
        for table in TABLES_IN_ORDER:
            try:
                # 각 테이블을 savepoint로 격리 → 한 테이블 실패해도 다음 테이블 진행 가능
                pc.execute(sa.text('SAVEPOINT sp_migrate'))
                migrate_table(sc, pc, table)
                pc.execute(sa.text('RELEASE SAVEPOINT sp_migrate'))
            except Exception as e:
                pc.execute(sa.text('ROLLBACK TO SAVEPOINT sp_migrate'))
                print(f'  {table}: ❌ 오류 - {e}')
        pc.commit()
    print('=== 완료 ===')

if __name__ == '__main__':
    main()
