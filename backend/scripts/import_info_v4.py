"""
extraction/info_v4/info_62.json → DB 업데이트 스크립트

매핑:
  지원내용   → support_detail (텍스트 변환)
  제출서류   → submission_docs_json
  우대사항   → bonus_points_json
  최대지원금  → amount_max_manwon (만원 정수)
  지원규모   → total_budget_text
  중복지원   → duplicate_policy_json
  모집일정   → rounds_json
  트랙      → info_tracks_json

사용법:
  python3 backend/scripts/import_info_v4.py
  python3 backend/scripts/import_info_v4.py --dry-run   # DB 변경 없이 확인만
"""

import json
import sqlite3
import argparse
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "startup_support.db"
INFO_JSON = Path(__file__).parent.parent.parent / "extraction" / "info_v4" / "info_62.json"


def support_detail_text(지원내용: list) -> str | None:
    """지원내용 배열 → 화면 표시용 텍스트"""
    if not 지원내용:
        return None
    lines = []
    for item in 지원내용:
        항목 = item.get("항목", "")
        내용 = item.get("내용", "")
        if 항목 and 내용:
            lines.append(f"• {항목}: {내용}")
        elif 내용:
            lines.append(f"• {내용}")
    return "\n".join(lines) if lines else None


def main(dry_run: bool = False):
    if not INFO_JSON.exists():
        print(f"❌ info_62.json 없음: {INFO_JSON}")
        return

    with open(INFO_JSON, encoding="utf-8") as f:
        info_data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # DB에 있는 공고 ID 목록
    cur.execute("SELECT announcement_id FROM announcements")
    db_ids = {row["announcement_id"] for row in cur.fetchall()}

    updated = 0
    skipped = 0
    not_in_db = []

    for ann_id, info in info_data.items():
        if ann_id not in db_ids:
            not_in_db.append(ann_id)
            continue

        # 필드 변환
        지원내용 = info.get("지원내용") or []
        제출서류 = info.get("제출서류") or []
        우대사항 = info.get("우대사항") or []
        최대지원금 = info.get("최대지원금") or {}
        지원규모 = info.get("지원규모") or {}
        중복지원 = info.get("중복지원") or {}
        모집일정 = info.get("모집일정") or []
        트랙 = info.get("트랙") or []

        support_detail = support_detail_text(지원내용)
        amount_max = 최대지원금.get("만원")  # int or None
        total_budget = 지원규모.get("값") if isinstance(지원규모, dict) else None

        if dry_run:
            print(f"[DRY] {ann_id}")
            print(f"  support_detail: {(support_detail or '')[:60]}...")
            print(f"  amount_max_manwon: {amount_max}")
            print(f"  total_budget_text: {total_budget}")
            print(f"  제출서류 수: {len(제출서류)}, 트랙 수: {len(트랙)}")
        else:
            cur.execute("""
                UPDATE announcements SET
                    support_detail        = ?,
                    submission_docs_json  = ?,
                    bonus_points_json     = ?,
                    amount_max_manwon     = ?,
                    total_budget_text     = ?,
                    duplicate_policy_json = ?,
                    rounds_json           = ?,
                    info_tracks_json      = ?
                WHERE announcement_id = ?
            """, (
                support_detail,
                json.dumps(제출서류, ensure_ascii=False) if 제출서류 else None,
                json.dumps(우대사항, ensure_ascii=False) if 우대사항 else None,
                amount_max,
                total_budget,
                json.dumps(중복지원, ensure_ascii=False) if 중복지원 else None,
                json.dumps(모집일정, ensure_ascii=False) if 모집일정 else None,
                json.dumps(트랙, ensure_ascii=False) if 트랙 else None,
                ann_id,
            ))

        updated += 1

    if not dry_run:
        conn.commit()
        print(f"✅ DB 업데이트 완료: {updated}건")
    else:
        print(f"\n[DRY RUN] 업데이트 예정: {updated}건")

    if skipped:
        print(f"⏭ 스킵: {skipped}건")
    if not_in_db:
        print(f"⚠️  DB에 없는 공고 {len(not_in_db)}건: {not_in_db[:5]}{'...' if len(not_in_db) > 5 else ''}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="DB 변경 없이 확인만")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
