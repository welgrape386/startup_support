# 프론트·AI 통합 테이블 정의서 v2 (설계 제안)

> 기준: 2026-10-24 첨부 ERD + 현재 구축한 FastAPI/SQLite 소스 + GitHub `welgrape386/startup_support` 최신 소스 + AI 스키마 v0.4.
> 본 문서는 **확정된 DB가 아닌 통합 설계안**입니다. `현재` 열은 백엔드 `app/models.py`에서 확인한 컬럼만 해당합니다. `신규 핵심`과 `추가 권장`은 아직 마이그레이션/구현되지 않았습니다.

## 테이블 및 관계 개요

| 테이블 | 한글명 | 지난주 명칭 | 상태 |
|---|---|---|---|
| `announcements` | 지원사업 공고 | `support_programs` | 현재 |
| `files` | 첨부파일 | `program_files` | 현재 |
| `texts` | 원문 텍스트 | `program_texts` | 현재+확장 |
| `conditions` | 신청자격 조건 | `eligibility_rules` | 현재+확장 |
| `user_requests` | 사용자 요청·추출 프로필 | `user_requests` | P1 설계 |
| `match_runs` | 매칭 실행 | `match_runs` | P1 설계 |
| `match_results` | 공고별 매칭 결과 | `match_results` | P1 설계 |
| `condition_checks` | 조건별 판정 | `condition_checks` | P1 설계 |

## 공통 설계 규칙

- 공고 연결키는 기존 SQLite의 문자열 `announcements.announcement_id` (`PBLN_...`)를 유지한다. 지난주 `program_id INTEGER` 구조를 곧바로 덮어쓰지 않는다.
- 현재 `conditions`는 공고당 **하나의 최신 스키마 JSON**, 여러 버전은 확장 테이블 `extraction_runs`에 보존하는 방향이다.
- `condition_json`, `profile_json`은 PostgreSQL 운영 DB에서 JSONB, SQLite 로컬 DB에서는 JSON을 권장한다.
- AI 미실행/실패/원문에 없음/원문 불명확은 다른 상태다. SQL NULL의 의미를 API에서 함께 설명한다.
- 실제 사용자의 자연어와 프로필에는 개인정보가 포함될 수 있다. 공개 데모에서는 원문/프로필의 지속 저장을 기본값으로 두지 말고 보존 필요성, 동의, 마스킹, 보존 기간을 합의한다.
- `match_runs` 이하 기록은 프론트 렌더링에 반드시 필요한 영구 테이블은 아니다. 정확도 비교/재현/감사를 수행할 때 저장하는 옵션이다.

## announcements — 지원사업 공고

| 컬럼 | 자료형 | NULL | 키/제약 | 기본값 | 의미 | 구현 상태 |
|---|---|:---:|---|---|---|---|
| `announcement_id` | `VARCHAR(32)` | N | PK |  | 기업마당 공고 ID (PBLN_...) / 현행 서비스 ID | 현재 |
| `source` | `VARCHAR(30)` | N |  | bizinfo | 수집 출처 | 현재 |
| `title` | `TEXT` | N |  |  | 공고명 | 현재 |
| `agency` | `TEXT` | Y |  |  | 소관 기관 | 현재 |
| `operator` | `TEXT` | Y |  |  | 수행 기관 | 현재 |
| `category_large` | `VARCHAR(100)` | Y |  |  | 지원사업 대분류 | 현재 |
| `category_medium` | `VARCHAR(100)` | Y |  |  | 지원사업 중분류 | 현재 |
| `target_name` | `TEXT` | Y |  |  | API 지원대상 | 현재 |
| `summary` | `TEXT` | Y |  |  | API 사업개요 | 현재 |
| `hashtags` | `TEXT` | Y |  |  | 해시태그 원문 | 현재 |
| `application_period_raw` | `TEXT` | Y |  |  | 접수기간 원문, 예산소진시까지 등 포함 | 현재 |
| `apply_start` | `DATE` | Y |  |  | 파싱 가능한 접수 시작일 | 현재 |
| `apply_end` | `DATE` | Y |  |  | 파싱 가능한 접수 종료일 | 현재 |
| `rolling` | `BOOLEAN` | N |  | false | 수시/상시 모집 여부. NULL과 혼동 금지 | 현재 |
| `application_method` | `TEXT` | Y |  |  | 신청 방법 | 현재 |
| `announcement_url` | `TEXT` | Y |  |  | 공고 상세 URL | 현재 |
| `application_url` | `TEXT` | Y |  |  | 실제 신청 URL | 현재 |
| `contact` | `TEXT` | Y |  |  | 문의처 | 현재 |
| `fetched_created_at` | `VARCHAR(30)` | Y |  |  | API 원천 등록 시각 원문 | 현재 |
| `fetched_updated_at` | `VARCHAR(30)` | Y |  |  | API 원천 수정 시각 원문 | 현재 |
| `raw_fields` | `JSON/JSONB` | N |  |  | API 수집 모든 필드 원형 보존 | 현재 |
| `support_types_json` | `JSON/JSONB` | Y |  |  | 융자·보조금·보증·교육·멘토링·공간·사업화·기타 | 추가 권장 |
| `amount_max_manwon` | `INTEGER` | Y |  |  | 사업별 1인·1건 지원액(만원), 추정 금지 | 추가 권장 |
| `total_budget_text` | `TEXT` | Y |  |  | 전체 예산 원문(개별 지원액과 구분) | 추가 권장 |
| `interest_rate` | `VARCHAR(100)` | Y |  |  | 융자형 이율 원문 | 추가 권장 |
| `support_detail` | `TEXT` | Y |  |  | 지원 내용/이차보전 등 | 추가 권장 |
| `status` | `VARCHAR(20)` | Y |  |  | 모집중/모집예정/마감, 산정 기준 필요 | 추가 권장 |
| `duplicate_policy_json` | `JSON/JSONB` | Y |  |  | 중복 수혜 가능·불가·조건부·미확인 및 근거 | 추가 권장 |
| `submission_docs_json` | `JSON/JSONB` | Y |  |  | 제출 서류 목록, 추출 완료 전에는 NULL | 추가 권장 |
| `bonus_points_json` | `JSON/JSONB` | Y |  |  | 우대·가점 목록, 신청자격 조건과 구분 | 추가 권장 |
| `rounds_json` | `JSON/JSONB` | Y |  |  | 차수별 일정 | 추가 권장 |
| `reviewed` | `BOOLEAN` | N |  | false | 사람의 조건/공고 검수 완료 여부 | 추가 권장 |
| `collected_at` | `TIMESTAMPTZ` | Y |  |  | 우리 시스템 수집 시점 | 추가 권장 |

## files — 첨부파일

| 컬럼 | 자료형 | NULL | 키/제약 | 기본값 | 의미 | 구현 상태 |
|---|---|:---:|---|---|---|---|
| `file_id` | `INTEGER` | N | PK |  | 첨부파일 ID | 현재 |
| `announcement_id` | `VARCHAR(32)` | N | FK→announcements.announcement_id |  | 연결 공고 | 현재 |
| `file_name` | `TEXT` | Y |  |  | 원본 파일명 | 현재 |
| `file_url` | `TEXT` | N |  |  | 첨부파일 URL | 현재 |
| `file_type` | `VARCHAR(16)` | Y |  |  | pdf/hwp/hwpx/docx 등 | 현재 |
| `file_role` | `VARCHAR(30)` | N |  |  | 공고문/기타첨부 구분 | 현재 |
| `sequence` | `INTEGER` | N |  |  | 같은 역할 내 파일 순서 | 현재 |
| `download_status` | `VARCHAR(32)` | N |  | not_downloaded | URL 수집과 실제 다운로드 상태 구분 | 현재 |
| `local_path` | `TEXT` | Y |  |  | 실제 다운로드한 파일의 안전한 로컬/스토리지 키 | 후속 선택 |
| `downloaded_at` | `TIMESTAMPTZ` | Y |  |  | 다운로드 일시 | 후속 선택 |

## texts — 원문 텍스트

| 컬럼 | 자료형 | NULL | 키/제약 | 기본값 | 의미 | 구현 상태 |
|---|---|:---:|---|---|---|---|
| `text_id` | `INTEGER` | N | PK |  | 원문 ID | 현재 |
| `announcement_id` | `VARCHAR(32)` | N | FK→announcements.announcement_id |  | 원문이 속한 공고. 현행 UNIQUE 있음 | 현재 |
| `content` | `TEXT` | Y |  |  | 원문 전체, 실패 시 NULL | 현재 |
| `source_format` | `VARCHAR(20)` | Y |  |  | 원본 포맷 | 현재 |
| `source_file_name` | `TEXT` | Y |  |  | 원본 파일명 | 현재 |
| `extraction_status` | `VARCHAR(80)` | N |  | not_attempted | 성공/실패/미시도 및 세부 상태 | 현재 |
| `suspected_incomplete` | `BOOLEAN` | N |  | false | 일부 내용 누락 의심 플래그 | 현재 |
| `extraction_error` | `TEXT` | Y |  |  | 텍스트 추출 실패 사유 | 현재 |
| `extracted_at` | `TIMESTAMP` | Y |  |  | 추출 시각 | 현재 |
| `file_id` | `INTEGER` | Y | FK→files.file_id |  | 첨부파일 텍스트면 연관 파일; HTML은 NULL | 추가 권장 |
| `source_kind` | `VARCHAR(30)` | N |  | attachment | attachment/html/manual/merged | 추가 권장 |
| `is_primary` | `BOOLEAN` | N |  | false | 해당 공고의 대표 텍스트 여부 | 추가 권장 |
| `section_name` | `VARCHAR(100)` | Y |  |  | 본문의 신청자격/지원내용 등 섹션 | 추가 권장 |

## conditions — 신청자격 조건

| 컬럼 | 자료형 | NULL | 키/제약 | 기본값 | 의미 | 구현 상태 |
|---|---|:---:|---|---|---|---|
| `condition_id` | `INTEGER` | N | PK |  | 공고 조건 레코드 ID | 현재 |
| `announcement_id` | `VARCHAR(32)` | N | FK→announcements.announcement_id; UNIQUE |  | 공고당 현재 조건 JSON 한 개 | 현재 |
| `schema_version` | `VARCHAR(20)` | Y |  |  | AI 스키마 버전 v0.4 | 현재 |
| `condition_json` | `JSON/JSONB` | Y |  |  | AI 추출 JSON 원형, 미추출 시 NULL | 현재 |
| `sido` | `VARCHAR(70)` | Y | INDEX |  | 단일 확정 지역일 때만 값 | 현재 |
| `business_registration` | `VARCHAR(60)` | Y | INDEX |  | 확정 가능 시 사업자등록 조건 검색용 | 현재 |
| `max_startup_months` | `INTEGER` | Y | INDEX |  | 업력 최대 개월(복수 트랙/예외면 NULL) | 현재 |
| `max_age` | `INTEGER` | Y | INDEX |  | 나이 상한(기준/트랙 확인 필요) | 현재 |
| `extraction_status` | `VARCHAR(30)` | N |  | not_extracted | 미추출/성공/실패/검수대기 | 현재 |
| `extracted_at` | `TIMESTAMP` | Y |  |  | 추출 일시 | 현재 |
| `source_text_id` | `INTEGER` | Y | FK→texts.text_id |  | 인용 검증 시 기준이 된 대표 원문 | 추가 권장 |
| `model_name` | `VARCHAR(100)` | Y |  |  | 추출 모델 | 추가 권장 |
| `prompt_version` | `VARCHAR(50)` | Y |  |  | 조건 추출 프롬프트 버전 | 추가 권장 |
| `quote_validation_status` | `VARCHAR(30)` | Y |  |  | 근거 원문 일치 검증 상태 | 추가 권장 |

## user_requests — 사용자 요청·추출 프로필

| 컬럼 | 자료형 | NULL | 키/제약 | 기본값 | 의미 | 구현 상태 |
|---|---|:---:|---|---|---|---|
| `request_id` | `BIGINT` | N | PK |  | 사용자 요청 ID | 신규 핵심 |
| `input_text` | `TEXT` | N |  |  | 사용자의 원본 자연어 | 신규 핵심 |
| `profile_json` | `JSON/JSONB` | Y |  |  | AI가 추출한 사용자 전체 프로필 및 evidence | 신규 핵심 |
| `age` | `INTEGER` | Y |  |  | 프로필에서 확정된 나이(기준일 판단 주의) | 신규 핵심 |
| `sido` | `VARCHAR(70)` | Y |  |  | 사용자 주거/창업예정지 중 어떤 종류인지 구분 필수 | 신규 핵심 |
| `sigungu` | `VARCHAR(70)` | Y |  |  | 확정된 시군구 | 신규 핵심 |
| `biz_stage` | `VARCHAR(50)` | Y |  |  | 예비창업/초기창업 등 UI 표시값 | 신규 핵심 |
| `industry_ksic_json` | `JSON/JSONB` | Y |  |  | KSIC 대분류 목록(최대 2개라는 AI 스키마 준수) | 신규 핵심 |
| `needs_json` | `JSON/JSONB` | Y |  |  | 자금/교육/공간 등 원하는 지원 | 신규 핵심 |
| `profile_status` | `VARCHAR(30)` | N |  | not_extracted | 사용자 조건 추출 상태; 미입력과 추출실패 구분 | 신규 핵심 |
| `created_at` | `TIMESTAMPTZ` | N |  | now() | 요청 생성 시각 | 신규 핵심 |

## match_runs — 매칭 실행

| 컬럼 | 자료형 | NULL | 키/제약 | 기본값 | 의미 | 구현 상태 |
|---|---|:---:|---|---|---|---|
| `run_id` | `BIGINT` | N | PK |  | 매칭 실행 ID | 신규 핵심 |
| `request_id` | `BIGINT` | N | FK→user_requests.request_id |  | 실행 입력 | 신규 핵심 |
| `execution_status` | `VARCHAR(30)` | N |  | running | running/success/failed | 신규 핵심 |
| `data_source` | `VARCHAR(20)` | N |  | live | live/mock; 평가에서 반드시 구분 | 신규 핵심 |
| `search_version` | `VARCHAR(50)` | Y |  |  | BM25/V1/V2/V3 버전 | 신규 핵심 |
| `judge_version` | `VARCHAR(50)` | Y |  |  | 판정 엔진 버전 | 신규 핵심 |
| `parser_version` | `VARCHAR(50)` | Y |  |  | 사용자 조건 추출 버전 | 신규 핵심 |
| `schema_version` | `VARCHAR(20)` | Y |  |  | 조건 스키마 버전 | 신규 핵심 |
| `data_snapshot` | `VARCHAR(80)` | Y |  |  | 342건 선정 스냅샷 식별자 | 신규 핵심 |
| `processing_time_ms` | `INTEGER` | Y |  |  | 응답 처리 시간 밀리초 | 신규 핵심 |
| `input_tokens` | `INTEGER` | Y |  |  | 투입 토큰수 | 신규 핵심 |
| `output_tokens` | `INTEGER` | Y |  |  | 출력 토큰수 | 신규 핵심 |
| `estimated_cost` | `NUMERIC(14,6)` | Y |  |  | 예상 비용 | 신규 핵심 |
| `cost_currency` | `VARCHAR(10)` | Y |  |  | USD/KRW 등 통화 구분 | 신규 핵심 |
| `summary_json` | `JSON/JSONB` | Y |  |  | 프론트 응답 상단 집계/요약 | 신규 핵심 |
| `coverage_json` | `JSON/JSONB` | Y |  |  | 검색 범위 sources/total/asOf/regions | 신규 핵심 |
| `started_at` | `TIMESTAMPTZ` | N |  | now() | 실행 시작 | 신규 핵심 |
| `completed_at` | `TIMESTAMPTZ` | Y |  |  | 완료 또는 실패 시각 | 신규 핵심 |
| `error_code` | `VARCHAR(60)` | Y |  |  | AI/검색/DB 실패 코드 | 신규 핵심 |

## match_results — 공고별 매칭 결과

| 컬럼 | 자료형 | NULL | 키/제약 | 기본값 | 의미 | 구현 상태 |
|---|---|:---:|---|---|---|---|
| `result_id` | `BIGINT` | N | PK |  | 개별 공고 추천 결과 ID | 신규 핵심 |
| `run_id` | `BIGINT` | N | FK→match_runs.run_id |  | 실행 ID | 신규 핵심 |
| `announcement_id` | `VARCHAR(32)` | N | FK→announcements.announcement_id |  | 대상 공고 | 신규 핵심 |
| `verdict` | `VARCHAR(30)` | N |  |  | 자격 충족/조건부/확인 필요/자격 미달 | 신규 핵심 |
| `score` | `NUMERIC(5,2)` | Y |  |  | 추천 점수 0~100(정책 정의 필요) | 신규 핵심 |
| `rank_number` | `INTEGER` | Y |  |  | 해당 실행 내 추천 순위 | 신규 핵심 |
| `headline` | `TEXT` | Y |  |  | 카드용 한줄 판정 문구 | 신규 핵심 |
| `reasons_json` | `JSON/JSONB` | Y |  |  | 근거 문장·chunkId 포함한 사유 배열 | 신규 핵심 |
| `cautions_json` | `JSON/JSONB` | Y |  |  | 주의할 점 배열 | 신규 핵심 |
| `exceptions_json` | `JSON/JSONB` | Y |  |  | 예외조항 배열 | 신규 핵심 |
| `created_at` | `TIMESTAMPTZ` | N |  | now() | 결과 생성일 | 신규 핵심 |

## condition_checks — 조건별 판정

| 컬럼 | 자료형 | NULL | 키/제약 | 기본값 | 의미 | 구현 상태 |
|---|---|:---:|---|---|---|---|
| `check_id` | `BIGINT` | N | PK |  | 조건별 판정 ID | 신규 핵심 |
| `result_id` | `BIGINT` | N | FK→match_results.result_id |  | 해당 공고의 매칭 결과 | 신규 핵심 |
| `condition_id` | `INTEGER` | Y | FK→conditions.condition_id |  | 조건 JSON 레코드; 미추출이면 NULL | 신규 핵심 |
| `condition_path` | `VARCHAR(255)` | Y |  |  | JSON 조건 위치(예: 나이, 트랙[0].조건.업력) | 신규 핵심 |
| `check_status` | `VARCHAR(30)` | N |  |  | pass/fail/unknown/conditional | 신규 핵심 |
| `user_value_json` | `JSON/JSONB` | Y |  |  | 비교 시 사용한 사용자 입력값 | 신규 핵심 |
| `required_value_json` | `JSON/JSONB` | Y |  |  | 공고 원문에서 추출한 요구조건 | 신규 핵심 |
| `reason` | `TEXT` | Y |  |  | 판정 이유 | 신규 핵심 |
| `evidence_quote` | `TEXT` | Y |  |  | 검증할 원문 근거 | 신규 핵심 |
| `evidence_verified` | `BOOLEAN` | Y |  |  | 텍스트에서 근거가 검증되었는지 (검증 전 NULL) | 신규 핵심 |
| `evidence_start` | `INTEGER` | Y |  |  | 공백 무시 정규화 텍스트상의 위치 / 기준 정의 필요 | 신규 핵심 |
| `evidence_end` | `INTEGER` | Y |  |  | 근거 종료 위치 / 기준 정의 필요 | 신규 핵심 |
| `created_at` | `TIMESTAMPTZ` | N |  | now() | 검사 결과 생성 시각 | 신규 핵심 |

## 확장 후보 테이블 (지금 바로 만들 필요 없음)

| 테이블 | 사용 조건 |
|---|---|
| `extraction_runs` | 모델/프롬프트별 조건 추출 원본 이력을 DB에서 비교할 때 |
| `notice_chunks` | RAG 인덱스를 공고·원문 테이블과 SQL FK로 연결해야 할 때 |
| `excluded_industries` | AI팀의 제외업종 참조 CSV를 DB 쿼리로 사용하기로 합의했을 때 |
| `eval_labels` | 사람 정답셋을 CSV가 아닌 DB에서 관리하기로 합의했을 때 |

## 인덱스·고유 제약 제안

- `announcements`: 현재 PK `announcement_id`, 조회 목적에 맞춰 `(apply_end)` 및 `(category_large, category_medium)` 선택.
- `files`: 현재 UNIQUE(`announcement_id`,`file_role`,`sequence`) 유지.
- `texts`: 현재 UNIQUE(`announcement_id`)는 공고당 여러 텍스트를 허용할 때 제거. `is_primary`는 공고당 true 1개만 허용하는 부분 인덱스(PostgreSQL) 제안.
- `conditions`: UNIQUE(`announcement_id`)는 현행 최신 조건 1개 구조에서는 유지.
- `match_results`: UNIQUE(`run_id`, `announcement_id`).
- `condition_checks`: 반복 검사/트랙 여부를 고려해 `condition_path`에 성급하게 UNIQUE를 걸지 않는다.

## 신구 구조 간 대표 차이

- `support_programs.program_id` (지난주 INTEGER) → `announcements.announcement_id` (현재 CSV 문자열 ID). 기존 데이터 무손실 유지.
- `eligibility_rules` (자격조건 1행씩) → `conditions.condition_json` (AI v0.4 통째). `condition_checks`는 `condition_id`와 `condition_path`로 연결.
- 지난주 `program_texts`의 파일별 N행 설계는 맞지만 현재 `texts`는 공고당 1행. 별도 마이그레이션 필수.
- `match_runs`, `match_results`, `condition_checks`의 저장 여부는 평가/히스토리 요구와 개인정보 정책 결정 후 확정.
