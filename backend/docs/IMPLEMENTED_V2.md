# 통합 ERD v2 — 실제 구현 상태 (2026-10-24)

| 테이블 | 상태 | 저장 예시 / 용도 |
|---|---|---|
| announcements | 구현·342건 유지 | 실제 기업마당 공고, 원본 21개 필드 JSON |
| files | 구현·661건 유지 | 공고 첨부파일 메타정보·링크 |
| texts | 구현·342상태(본문 307건) 유지 | 공고별 복수 본문 가능, is_primary, file_id, source_kind 추가 |
| conditions | 구현·342상태(실제 JSON 0건) | 스키마 v0.4 JSON+검색용 컬럼, model_name·prompt_version·source_text_id 추가 |
| user_requests | 신규 구현·기본 0건 | 사용자 원문·프로필 JSON, 저장 기본 비활성 |
| match_runs | 신규 구현·기본 0건 | 실행/검색 버전·데이터 스냅샷 |
| match_results | 신규 구현·기본 0건 | 실행별 후보·판정·관련도 점수·순위 |
| condition_checks | 신규 구현·기본 0건 | 실제 조건 판정 연결 시 조건 경로·근거 기록 |

`announcements`에도 `support_types_json`, `amount_max_manwon`, `total_budget_text`, `interest_rate`, `support_detail`, `status`, `duplicate_policy_json`, `submission_docs_json`, `bonus_points_json`, `rounds_json`, `reviewed`, `collected_at`가 추가되었습니다. 대부분은 현재 CSV만으로 신뢰성 있게 채울 수 없으므로 NULL로 남겨 두었습니다.

**특기 사항:** SQLite 기존 스키마에서 `conditions.source_text_id`는 컬럼만 추가했고 FK 제약을 자동 적용하지 않았습니다. 새 빈 DB의 SQLAlchemy 모델은 FK 관계를 정의하지만 기존 SQLite 마이그레이션에서는 호환성 때문에 컬럼만 추가했습니다. 다음 마이그레이션에 배치 테이블 재작성으로 물리적 FK를 추가할 수 있습니다. 기존 데이터는 유지됩니다.

## 실제 동작하는 프론트 계약

`POST /api/support-match`는 기존 프론트의 `SupportMatchRequest`를 받아 아래 구조를 반환합니다.

- `profile`: 나이·거주지역·예비창업·업종 등 간이 규칙 추출
- `missing`: 찾지 못한 핵심 프로필 필드
- `results`: 키워드 관련도 높은 DB 공고 최대 12건 (모두 `확인 필요`)
- `conditional`: 빈 배열, `excluded`: 빈 배열
- `nextSteps`: 빈 배열 (조건 변경에 따른 재판정 기능 미구현)
- `summary`: eligibleCount=0, checkCount=results 개수
- `coverage`: 원본 대상 342건 정보
- `meta`: dataSource='mock', parser='rule' (실제 AI 검증이 아니라는 신호)
- `demoNotice`: 프론트 이전 버전과 호환되는 **추가 필드**, 로컬 실험 상태 설명

공고의 제목·사업개요·기간은 실제 DB 값입니다. 지원 유형은 공고 표현을 단순 규칙으로 분류하므로 검증된 정규화값으로 취급하면 안 됩니다. score는 **키워드 검색 순위를 위한 값**이지 신뢰도/자격 충족 확률이 아닙니다.

## React 변경 파일 (독립 frontend 복사본)

- `frontend/vite.config.ts`: `/api` → `http://127.0.0.1:8000` 로컬 프록시
- `frontend/src/pages/SupportMatchResults.tsx`: 실제 판정 미연동을 설명하는 상시 표시 경고 배너와 안내 문구

그 외 프론트 파일은 제공한 ZIP 스냅샷을 유지했습니다. 원본 GitHub에 푸시하지 않았습니다.

## 검증

- `python -m scripts.upgrade_v2`: 데이터 건수 불변 / 8개 테이블 / SQLite FK 오류 0건
- `python -m pytest -q`: 8개 테스트 통과
- API `POST /api/support-match`: HTTP 200 + 프론트가 예상하는 필수 top-level keys
- 기존 DB 조건 JSON 0건이므로 모든 공고 `verdict='확인 필요'`
- 프론트 `npm ci` 네트워크 설치 제한으로 로컬 React 빌드는 미검증; Windows에서 실행 확인 필요

## 향후 AI팀 연결

- 조건 JSON을 실제로 적재한 뒤 검증 → 안전한 자격 판정 코드 또는 AI팀 판정 함수 연동
- 김나애님 검색 코드를 `app/local_demo.py`의 단순 키워드 검색 대신 검색 어댑터로 연동
- 판정 근거 인용은 `texts` 실제 원문과 일치 검증한 값만 사용
- 상단 3줄 요약, 조건부/제외, 시나리오 변경 등은 지금까지 미연동
