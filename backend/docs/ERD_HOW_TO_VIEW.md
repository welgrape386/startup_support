# 실제 데이터베이스 ERD 확인하기 (V4 + Schema v0.4)

## DBeaver에서 보기
1. DBeaver Community 설치: https://dbeaver.io/download/
2. **Database > New Database Connection > SQLite**.
3. 로컬에 압축 해제된 `backend/data/startup_support.db`를 지정.
4. 연결 후 왼쪽 **Tables**를 펼쳐, `announcements`, `files`, `texts`, `conditions`, `user_requests`, `match_runs`, `match_results`, `condition_checks` 테이블을 선택.
5. 컨텍스트 메뉴 **ER Diagram** 또는 데이터베이스의 **Diagram** 탭에서 다이어그램 확인.
6. `announcements` 열 보기: `region`, `seoul_gu`, `has_text`, `support_types`, `카테고리`, 9개 플래그를 찾으세요.

> 주의: 연결 전 `backend/` 폴더에서 `python -m alembic upgrade head`를 먼저 실행하여 실제 스키마를 생성/갱신하세요. 단순 PDF/ERDCloud 설계도와 실제 DB는 차이가 있을 수 있습니다.

## SQL로 확인하기
`python -m scripts.inspect_erd` : 실제 DB 테이블, 컬럼, FK, 행 수를 터미널에서 점검하고 `docs/ERD_ACTUAL.mmd`를 생성합니다.

## 데이터 모델
핵심 FK: `files.announcement_id`, `texts.announcement_id`, `conditions.announcement_id` → `announcements`; `match_runs.request_id` → `user_requests`; `match_results.run_id` → `match_runs`; `match_results.announcement_id` → `announcements`; `condition_checks.result_id` → `match_results`. 데이터베이스에 정의된 FK만 ERD에서 연결되어 보입니다.
