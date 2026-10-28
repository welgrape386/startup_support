> ⚠️ **구 통합 설계 문서입니다.** 이 ZIP에는 8개 테이블을 구현한 코드와 로컬 검색 데모가 추가되었습니다. 현재 실제 상태는 [IMPLEMENTED_V2.md](IMPLEMENTED_V2.md)를 우선 참고하세요.

# ERDCloud에서 지난주 ERD 수정하는 순서 — 통합안 v2

**기본 원칙:** 지난주 `support_programs`, `program_files`, `program_texts`, `eligibility_rules`, `user_requests`, `match_runs`, `match_results`, `condition_checks` 프로젝트는 먼저 **복제**하세요. 지난주 설계본과 현재 실행 중인 SQLite를 모두 보존합니다. 본 설명은 ERDCloud 화면에서 수동 수정할 표와 관계를 알려주는 안내이며, 기존 SQLite에 적용한 SQL 마이그레이션은 아닙니다.

기존 작업 주소: https://www.erdcloud.com/d/jNesBTpGy774h5GQF

## 0. 이름 통일

| 지난주 ERD | ERDCloud 통합안 이름 | 현재 구현 | 작업 |
|---|---|---|---|
| support_programs | announcements | 존재 | 테이블 이름 변경, 현행 컬럼을 기준으로 보완 |
| program_files | files | 존재 | 테이블 이름 변경, `sequence` 사용 |
| program_texts | texts | 존재 | 이름 변경, 파일별 1:N 확장 계획 표시 |
| eligibility_rules | conditions | 존재 | 구 방식 대체: 원본 JSON + 4개 검색용 값 |
| user_requests | user_requests | 없음 | 기존 설계를 업데이트하고 신규로 구현 예정 |
| match_runs | match_runs | 없음 | 버전·스냅샷 정보 보완 |
| match_results | match_results | 없음 | 기존 구조 보완 |
| condition_checks | condition_checks | 없음 | `rule_id` 대신 `condition_id + condition_path` |

## 1. announcements 수정

1. **기존 PK `program_id INTEGER`를 그대로 쓰지 마세요.** 현재 실제 데이터베이스 PK는 `announcement_id VARCHAR(32)`이며 기업마당 원본 `PBLN_...`을 그대로 저장합니다.
2. `source_name`은 `source VARCHAR(30)`로 정리하고, 기존 CSV의 공고 ID가 충분한 범위에서는 `external_program_id`를 별도 PK로 중복 도입하지 않습니다. 향후 K-Startup 추가 시 `(source, external_id)` 형태를 다시 검토합니다.
3. 지난주 공고 컬럼에 없었던 현행 컬럼(대·중분류, 지원대상, 해시태그, 접수기간 원문, 신청방법, 문의처, 원본 API JSON, 원본 생성/수정일)을 `TABLE_DEFINITION.md`의 `현재` 항목 기준으로 추가하세요.
4. 프론트 `SupportProgram`에서 필요한 `support_types_json`, `amount_max_manwon`, `total_budget_text`, `interest_rate`, `support_detail`, `status`, `duplicate_policy_json`, `submission_docs_json`, `bonus_points_json`, `rounds_json`, `reviewed`, `collected_at`는 `추가 권장`으로 표기하세요. 현행 API에 데이터가 모두 있는 것은 아닙니다.
5. `apply_end=NULL` = 무조건 상시모집이 아닙니다. `rolling`과 `application_period_raw`를 함께 보존하세요.

## 2. files 수정

1. `program_files` → `files` 이름 변경.
2. PK `file_id INTEGER`, FK `announcement_id VARCHAR(32)`로 변경.
3. `file_name`, `file_url`, `file_type`, `download_status` 유지.
4. `file_order` → 현재 코드의 `sequence INTEGER`; `file_role VARCHAR(30)` 추가.
5. UNIQUE `(announcement_id, file_role, sequence)` 유지.
6. 파일 URL은 다운로드 완료가 아님. `local_path`·`downloaded_at`은 다운로드를 실제 관리할 때만 추가.

## 3. texts 수정 — 먼저 관계 검토

1. `program_texts` → `texts`; FK `program_id` → `announcement_id VARCHAR(32)`.
2. 현재 코드는 **공고당 1개 텍스트** 구조이므로 `announcement_id UNIQUE`가 걸려 있음. 파일별 추출 원문을 지원하려면 UNIQUE 제거 및 1:N 관계로 변경해야 함(추후 Alembic 마이그레이션).
3. 기존 현행 컬럼 `text_id`, `content`, `source_format`, `source_file_name`, `extraction_status`, `suspected_incomplete`, `extraction_error`, `extracted_at` 유지.
4. `file_id INTEGER NULL FK→files.file_id`, `source_kind`, `is_primary`, `section_name` 추가 권장.
5. 기존 `chunk_number`는 본문 자체를 나누는 용도로 쓸지 RAG 청크용인지 구분. **RAG 청크는 `notice_chunks`로 분리하는 안**을 AI 검색팀과 검토.
6. 현재 `GET /api/v1/announcements/{id}/text`가 `.scalar()`로 1행만 읽으므로, 1:N으로 바꾼다면 **대표 원문 선택 로직까지** 변경해야 함.

## 4. eligibility_rules → conditions 재설계 (가장 중요한 변경)

1. 지난주 `rule_group_number`, `group_operator`, `rule_type`, `minimum_value`, `maximum_value`, `comparison_operator`, `expected_value` 등 **원문 조건을 한 행씩 분해하는 컬럼을 통합 원본의 필수 구조에서 제거**. 해당 구형 테이블을 지금 DB에 실수로 생성하지 마세요.
2. 이름 `conditions`, PK `condition_id INTEGER`, FK `announcement_id VARCHAR(32) UNIQUE`.
3. `schema_version`, `condition_json JSONB(운영)/JSON(로컬)`, `extraction_status`, `extracted_at` 추가.
4. 검색용 `sido`, `business_registration`, `max_startup_months`, `max_age` 추가. 단, 트랙/OR/복수 범위를 단일 값으로 오해할 때는 **NULL**.
5. 최신 AI 스키마 v0.4의 네 상태값 `있음`, `없음`, `불명확`, `대안조건`과 `not_extracted`(미실행)를 혼동하지 말 것.
6. 추출의 모델·프롬프트 버전, 원문 근거 검증을 위해 `source_text_id`, `model_name`, `prompt_version`, `quote_validation_status` 보완 권장.

## 5. user_requests 갱신

1. 지난주 `input_text`, `extracted_profile_json` 취지는 유지하되 JSON 컬럼명을 `profile_json`으로 일원화.
2. 프론트 `UserProfile`은 `age`, `sido`, `sigungu`, `bizStage`, `needs`, `targetGroups`, `freeText` 및 evidence 등 복합 객체이므로 한두 개 문자열 컬럼만으로 표현하지 말 것.
3. 자주 조회할 `age`, `sido`, `sigungu`, `biz_stage`, `industry_ksic_json`, `needs_json`을 보조 컬럼으로 제안.
4. 현재 프론트는 브라우저의 상태와 로컬 저장을 일부 사용하므로 **DB 영구 저장은 아직 필수 아님**. 사용자 원문 저장에는 개인정보 처리 범위와 보존기간 결정이 필요.

## 6. match_runs 갱신

1. `request_id` FK를 연결.
2. 기존 `model_name`, `prompt_version`, `processing_time`에 더해 `data_source`, `search_version`, `judge_version`, `parser_version`, `schema_version`, `data_snapshot` 컬럼을 추가하는 방향으로 변경.
3. `processing_time_ms`, `input_tokens`, `output_tokens`, `estimated_cost`, `cost_currency`로 단위/통화 확정.
4. 프론트의 `summary`, `coverage`, `meta`는 API 응답에 필수지만, 영구 저장할지 계산할지는 별도 정책. 평가 재현용 저장 시 `summary_json`, `coverage_json` 권장.

## 7. match_results 갱신

1. 기존 `run_id`, `program_id` → `run_id`, `announcement_id` FK로 연결.
2. `verdict`는 프론트 실제 타입의 `자격 충족`, `확인 필요`, `조건부`, `자격 미달` 값을 우선 기준으로 사용. 화면 신호등과 API enum은 혼용하지 말 것.
3. `score`, `rank_number`, `headline`, `reasons_json`, `cautions_json`, `exceptions_json` 제안.
4. UNIQUE `(run_id, announcement_id)`.
5. 사용자에게 보여줄 지원 내용/기관은 중복 저장하지 않고 `announcements`에서 조합.

## 8. condition_checks 수정

1. `rule_id FK→eligibility_rules.rule_id`를 **삭제/대체**.
2. `condition_id FK→conditions.condition_id`와 `condition_path VARCHAR(255)` 사용. `condition_path`는 실제 AI팀 JSON 구조에서 조건 위치를 가리킴.
3. `check_status`는 코드 내부의 `pass/fail/unknown/conditional`로 표현하고, 화면의 종합 신호등은 `match_results.verdict`로 별도 유지.
4. `user_value_json`, `required_value_json`, `reason`, `evidence_quote`, `evidence_verified`, 위치 기록 추가 권장.
5. 실제로 조건에 대한 증거가 없으면 `evidence_quote`를 가짜로 채우지 말 것.

## 9. ERDCloud에서 관계선 다시 연결

| 부모 1 | 자식 N | FK / 참고 |
|---|---|---|
| announcements | files | files.announcement_id NOT NULL |
| announcements | texts | texts.announcement_id NOT NULL (장기 1:N) |
| files | texts | texts.file_id NULL (파일 아닌 HTML 가능) |
| announcements | conditions | conditions.announcement_id UNIQUE (0..1 현재 조건) |
| texts | conditions | conditions.source_text_id NULL |
| user_requests | match_runs | match_runs.request_id NOT NULL |
| match_runs | match_results | match_results.run_id NOT NULL |
| announcements | match_results | match_results.announcement_id NOT NULL |
| match_results | condition_checks | condition_checks.result_id NOT NULL |
| conditions | condition_checks | condition_checks.condition_id NULL (미추출 예외) |

## 10. 실제 SQLite 적용 순서 (ERD 편집 ≠ DB 변경)

- 단계 A: ERDCloud **복제→테이블/관계 수정→팀 검토**. 실제 데이터 수정 없음.
- 단계 B: `data/startup_support.db` 별도 복사본 백업(342 공고, 307 원문 보존) 및 `alembic current` 확인.
- 단계 C: 신규 `user_requests`, `match_runs`, `match_results`, `condition_checks` Alembic migration 작성, 업그레이드/다운그레이드 테스트.
- 단계 D: 필요가 확정된 경우에만 `texts` 1:N 마이그레이션 수행. 현행 API의 `.scalar()`와 기존 적재 스크립트를 함께 수정·테스트.
- 단계 E: 부가 공고 정보/조건 버전 기록 컬럼은 추출 산출물과 필드 매핑 검토 후 추가. 신규 입력은 NULL로 시작하고 **값을 꾸며내지 않음**.
- 단계 F: 프론트 계약을 실제 JSON으로 검증한 뒤 별도 브랜치에서 통합. main 직접 덮어쓰기 금지.
