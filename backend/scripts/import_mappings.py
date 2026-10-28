"""Import the RAG teammates' region_map.csv and category_map.csv by announcement ID.

Run from backend/, after `alembic upgrade head`:
  python -m scripts.import_mappings --region data/region_map.csv --category data/category_map.csv --dry-run
  python -m scripts.import_mappings --region data/region_map.csv --category data/category_map.csv

The maps themselves are supplied by teammates; no values are invented. Strict mode
requires one mapping per announcement and rejects unknown IDs/duplicates.
"""
import argparse
import csv
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from sqlalchemy import select
from app.db import SessionLocal, engine
from app.models import Announcement, CATEGORY_FIELD_TO_ATTR

ID_COLS = ('announcement_id', 'pblancId', 'pblanc_id', '공고ID', '공고_id', 'id', 'program_id', '공고번호')
CATEGORY_COLS = ('카테고리', 'category', 'categories', 'support_types', 'supportTypes', '지원유형', '카테고리명')
CATEGORIES = set(CATEGORY_FIELD_TO_ATTR)
REGIONS = {'서울', '전국', '타지역'}


def read_csv(path: Path):
    if not path.exists():
        raise ValueError(f'CSV 파일 없음: {path}')
    for encoding in ('utf-8-sig', 'cp949'):
        try:
            with path.open('r', encoding=encoding, newline='') as f:
                reader = csv.DictReader(f)
                fields = [col.strip() for col in (reader.fieldnames or [])]
                rows = [{k.strip(): (v or '').strip() for k, v in row.items() if k is not None} for row in reader]
                return fields, rows
        except UnicodeDecodeError:
            continue
    raise ValueError(f'인코딩 확인 필요: {path}')


def identify(fields, choices):
    return next((col for col in choices if col in fields), None)


def load_map(path, kind):
    fields, rows = read_csv(path)
    id_key = identify(fields, ID_COLS)
    if not id_key:
        raise ValueError(f'{kind}: 공고 ID 컬럼을 찾을 수 없음. 실제 컬럼: {fields}')
    if kind == 'region':
        required = {'region', 'seoul_gu', 'has_text'}
        if not required.issubset(fields):
            raise ValueError(f'region_map 필수 컬럼 누락: {required-set(fields)}')
    else:
        cat_key = identify(fields, CATEGORY_COLS)
        if not cat_key:
            raise ValueError(f'category_map 카테고리 컬럼 없음. 실제 컬럼: {fields}')
    out = {}
    for index, row in enumerate(rows, start=2):
        aid = row.get(id_key, '')
        if not aid:
            raise ValueError(f'{kind}: {index}행 공고 ID 누락')
        if aid in out:
            raise ValueError(f'{kind}: 중복 공고 ID {aid}')
        if kind == 'region':
            region = row['region']
            gu = row['seoul_gu']
            flag = row['has_text']
            if region not in REGIONS:
                raise ValueError(f'{kind}: {index}행 지역값 오류: {region!r}')
            if flag not in {'0','1'}:
                raise ValueError(f'{kind}: {index}행 has_text는 0/1이어야 함: {flag!r}')
            if gu and region != '서울':
                raise ValueError(f'{kind}: {index}행 구 제한인데 지역이 서울 아님: {region}, {gu}')
            out[aid] = {'region': region, 'seoul_gu': ','.join(x.strip() for x in gu.split(',') if x.strip()) or None, 'has_text': flag == '1'}
        else:
            parts = [p.strip() for p in row[cat_key].split(',') if p.strip()]
            invalid = sorted(set(parts) - CATEGORIES)
            if invalid:
                raise ValueError(f'{kind}: {index}행 미등록 카테고리: {invalid}; 허용={sorted(CATEGORIES)}')
            # The 9 binary columns in the teammate CSV are authoritative and must
            # agree exactly with the readable '카테고리' column, when all nine exist.
            has_flags = [name for name in CATEGORY_FIELD_TO_ATTR if name in fields]
            if has_flags and len(has_flags) != 9:
                raise ValueError(f'{kind}: 0/1 플래그 9칸 중 {len(has_flags)}칸만 존재합니다')
            if has_flags:
                for name in CATEGORY_FIELD_TO_ATTR:
                    flag = row[name]
                    if flag not in ('0', '1'):
                        raise ValueError(f'{kind}: {index}행 {name}은 0/1이어야 함: {flag!r}')
                    if (flag == '1') != (name in parts):
                        raise ValueError(f'{kind}: {index}행 {name} 0/1 값이 카테고리 문자값과 불일치')
            out[aid] = list(dict.fromkeys(parts))
    return out


def backup_sqlite():
    import os
    if os.getenv('SKIP_MAPPING_BACKUP') == '1':
        return None
    db_url = str(engine.url)
    if not db_url.startswith('sqlite:///') or db_url.endswith(':memory:'):
        return None
    dbpath = Path(db_url.removeprefix('sqlite:///'))
    if not dbpath.is_file():
        raise ValueError(f'SQLite DB 없음: {dbpath}')
    backup = dbpath.with_name(dbpath.stem + '_before_mapping_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.db')
    with sqlite3.connect(dbpath) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    return backup


def import_mappings(region_path: Path, category_path: Path, dry_run=False, allow_partial=False):
    region = load_map(region_path, 'region')
    category = load_map(category_path, 'category')
    with SessionLocal() as session:
        db_ids = set(session.scalars(select(Announcement.announcement_id)).all())
        unknown = (set(region) | set(category)) - db_ids
        if unknown:
            raise ValueError(f'DB에 존재하지 않는 공고 ID {len(unknown)}건: {sorted(unknown)[:5]}')
        if not allow_partial:
            for name, data in [('region_map', region), ('category_map', category)]:
                missing = db_ids - set(data)
                if missing:
                    raise ValueError(f'{name}: DB {len(db_ids)}건 중 누락 {len(missing)}건; 예시: {sorted(missing)[:5]}. 일부만 적재하려면 --allow-partial')
        print(f'Validated: DB {len(db_ids)}건, region_map {len(region)}건, category_map {len(category)}건')
        print('Region distribution:', dict(Counter(x['region'] for x in region.values())))
        print('Category distribution:', dict(Counter(v for cats in category.values() for v in cats)))
        if dry_run:
            print('DRY RUN: DB 수정 없음')
            return {'db':len(db_ids),'region':len(region),'category':len(category),'dry_run':True}
        backup = backup_sqlite()
        if backup:
            print('SQLite 백업:', backup)
        for a in session.scalars(select(Announcement)).all():
            if a.announcement_id in region:
                for key,val in region[a.announcement_id].items():
                    setattr(a,key,val)
            if a.announcement_id in category:
                cats = category[a.announcement_id]
                a.support_types = cats
                a.category_display = ', '.join(cats)
                for name, attr in CATEGORY_FIELD_TO_ATTR.items():
                    setattr(a, attr, int(name in cats))
        session.commit()
        print('Import complete. Previously imported values on unmapped rows remain unchanged.')
        return {'db':len(db_ids),'region':len(region),'category':len(category),'dry_run':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region', type=Path, required=True)
    parser.add_argument('--category', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    import_mappings(args.region, args.category, args.dry_run, args.allow_partial)


if __name__ == '__main__':
    main()
