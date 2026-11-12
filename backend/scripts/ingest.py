"""Idempotent Bizinfo 342-snapshot loader; optionally load extracted condition JSONs."""
import argparse
import csv
import json
import re
from datetime import datetime, date
from pathlib import Path
from sqlalchemy import select, func
from app.condition_utils import projection, validate_condition
from app.db import Base, create_db_engine
from app.models import Announcement, AnnouncementFile, AnnouncementText, Condition
from sqlalchemy.orm import Session

PROJECT = Path(__file__).resolve().parents[1]


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def clean(s: str | None):
    return s.strip() if s and s.strip() else None


def parse_period(period: str | None):
    if not period:
        return None, None, False
    m = re.fullmatch(r'\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})\s*', period)
    if m:
        try:
            return date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2)), False
        except ValueError:
            pass
    return None, None, bool(re.search(r'상시|예산\s*소진|연중|수시', period))


def file_pairs(r: dict):
    for role, nkey, ukey in [('print', 'printFileNm', 'printFlpthNm'), ('attachment', 'fileNm', 'flpthNm')]:
        names = (r.get(nkey) or '').split('@') if r.get(nkey) else []
        urls = (r.get(ukey) or '').split('@') if r.get(ukey) else []
        # No anonymous file rows: no URL means no retrievable file metadata.
        for sequence, url in enumerate(urls):
            if not url.strip():
                continue
            name = names[sequence].strip() if sequence < len(names) and names[sequence].strip() else None
            extension = name.rsplit('.', 1)[-1].lower() if name and '.' in name else None
            yield role, sequence, name, url.strip(), extension


def rows_to_announcements(session: Session, rows: list[dict]):
    ids = set()
    for r in rows:
        ann_id = clean(r.get('pblancId'))
        if not ann_id or ann_id in ids:
            raise ValueError(f'CSV 공고 ID 누락/중복: {ann_id}')
        ids.add(ann_id)
        a = session.get(Announcement, ann_id)
        if a is None:
            a = Announcement(announcement_id=ann_id, title=r.get('pblancNm') or '제목 없음', raw_fields={})
            session.add(a)
        start, end, rolling = parse_period(r.get('reqstBeginEndDe'))
        a.title = r.get('pblancNm') or '제목 없음'
        a.agency = clean(r.get('jrsdInsttNm'))
        a.operator = clean(r.get('excInsttNm'))
        a.category_large = clean(r.get('pldirSportRealmLclasCodeNm'))
        a.category_medium = clean(r.get('pldirSportRealmMlsfcCodeNm'))
        a.target_name = clean(r.get('trgetNm'))
        a.summary = clean(r.get('bsnsSumryCn'))
        a.hashtags = clean(r.get('hashtags'))
        a.application_period_raw = clean(r.get('reqstBeginEndDe'))
        a.apply_start, a.apply_end, a.rolling = start, end, rolling
        a.application_method = clean(r.get('reqstMthPapersCn'))
        a.announcement_url = clean(r.get('pblancUrl'))
        a.application_url = clean(r.get('rceptEngnHmpgUrl'))
        a.contact = clean(r.get('refrncNm'))
        a.fetched_created_at = clean(r.get('creatPnttm'))
        a.fetched_updated_at = clean(r.get('updtPnttm'))
        a.raw_fields = dict(r)
        session.flush()
        existing_files = {(f.file_role, f.sequence): f for f in session.scalars(select(AnnouncementFile).where(AnnouncementFile.announcement_id == ann_id)).all()}
        for role, seq, name, url, ext in file_pairs(r):
            obj = existing_files.pop((role,seq),None)
            if obj is None:
                obj = AnnouncementFile(announcement_id=ann_id, file_role=role, sequence=seq, file_url=url)
                session.add(obj)
            obj.file_name, obj.file_url, obj.file_type = name,url,ext
            # Never label URLs as downloaded files.
            obj.download_status = 'not_downloaded'
        for stale in existing_files.values():
            session.delete(stale)
        if session.scalar(select(Condition).where(Condition.announcement_id == ann_id)) is None:
            session.add(Condition(announcement_id=ann_id, extraction_status='not_extracted'))
    return ids


def ingest_texts(session: Session, report: Path, texts_dir: Path, allowed_ids: set[str]):
    rows = csv_rows(report)
    if len(set(r['공고ID'] for r in rows)) != len(rows):
        raise ValueError('원문 추출 보고서 공고ID 중복')
    if set(r['공고ID'] for r in rows) != allowed_ids:
        raise ValueError('공고 스냅샷과 추출 보고서의 공고 ID 집합이 다릅니다')
    count = 0
    for r in rows:
        ann_id = r['공고ID']
        obj = session.scalar(select(AnnouncementText).where(AnnouncementText.announcement_id == ann_id).order_by(AnnouncementText.is_primary.desc(), AnnouncementText.text_id.asc()))
        if obj is None:
            obj = AnnouncementText(announcement_id=ann_id)
            session.add(obj)
        status = clean(r['상태']) or 'not_attempted'
        content = None
        if status == '성공':
            path = texts_dir / f'{ann_id}.txt'
            if not path.is_file():
                raise FileNotFoundError(f'성공으로 보고됐지만 파일 없음: {path}')
            content = path.read_text(encoding='utf-8')
            count += 1
        obj.content = content
        obj.source_format = clean(r.get('형식'))
        obj.source_file_name = clean(r.get('파일명'))
        obj.extraction_status = status
        obj.extraction_error = clean(r.get('오류'))
        obj.suspected_incomplete = r.get('일부누락의심', '').lower() == 'true'
        obj.extracted_at = None  # v8 snapshot has no per-file extraction timestamp.
    return count


def load_conditions_file(path: Path):
    if path.suffix.lower() == '.jsonl':
        return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, list): return data
    if isinstance(data, dict) and isinstance(data.get('results'), list): return data['results']
    if isinstance(data, dict) and '공고ID' in data: return [data]
    raise ValueError('조건 JSON은 객체, 객체 배열, {"results": [...]} 또는 JSONL이어야 합니다')


def ingest_conditions(session: Session, path: Path, allowed_ids: set[str]):
    rows = load_conditions_file(path)
    used = set()
    for data in rows:
        ann_id = data.get('공고ID') if isinstance(data, dict) else None
        if ann_id not in allowed_ids:
            raise ValueError(f'선정 342건에 없는 공고ID: {ann_id}')
        if ann_id in used:
            raise ValueError(f'추출 결과 중복 공고ID: {ann_id}')
        used.add(ann_id)
        validate_condition(data, ann_id)
        obj = session.scalar(select(Condition).where(Condition.announcement_id == ann_id))
        if obj is None:
            obj = Condition(announcement_id=ann_id)
            session.add(obj)
        obj.condition_json = data
        obj.schema_version = data['스키마버전']
        obj.extraction_status = 'extracted'  # schema-shape validation, NOT human review.
        obj.extracted_at = datetime.now()
        for key, value in projection(data).items():
            setattr(obj, key, value)
    return len(used)


def main():
    ap = argparse.ArgumentParser(description='Load Bizinfo 342-announcement snapshot and optionally condition JSON results')
    ap.add_argument('--csv', type=Path, default=PROJECT/'data/selected_342.csv')
    ap.add_argument('--report', type=Path, default=PROJECT/'data/extract_report.csv')
    ap.add_argument('--texts-dir', type=Path, default=PROJECT/'data/texts')
    ap.add_argument('--conditions', type=Path, default=None)
    ap.add_argument('--db-url', type=str, default=None)
    args = ap.parse_args()
    rows = csv_rows(args.csv)
    if not rows: raise ValueError('CSV에 공고가 없습니다')
    engine = create_db_engine(args.db_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ids = rows_to_announcements(session, rows)
        success = ingest_texts(session,args.report,args.texts_dir,ids)
        c_count = ingest_conditions(session,args.conditions,ids) if args.conditions else 0
        session.commit()
        counts = {table: session.scalar(select(func.count()).select_from(model)) for table,model in [('announcements',Announcement),('files',AnnouncementFile),('texts',AnnouncementText),('conditions',Condition)]}
    print(json.dumps({'csv_selected':len(ids),'text_success':success,'text_missing_or_failed':len(ids)-success,'new_conditions_loaded':c_count,'database_table_counts':counts}, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
