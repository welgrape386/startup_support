# 창업지원사업 백엔드 초기본 (2026-10-24)

**성격:** 첨부 기업마당 데이터와 AI팀 v8 원문추출 결과를 사용하는 **독립 실행 가능한 FastAPI + SQLAlchemy 프로젝트**. 원본 프론트 `welgrape386/startup_support` 저장소는 변경하지 않았습니다.

## 확정된 범위와 현재 한계

- 전체 기업마당 API CSV 1,477건에서 AI팀 v8 `extract_report.csv`의 공고ID로 **342건을 선택**해 저장했습니다. 이전 314건은 최신 스키마 v0.1의 대상 확대 전 범위이며, 이 프로젝트는 **342건 스냅샷을 채택**했습니다.
- announcements: 342건 / files: 661건 (본문출력파일 342 + 첨부파일 319)
- texts: 성공 본문 307건, 실패·누락 35건을 **원문 없음 상태로** 별도 기록. 일부 누락 의심 문서 5건 표시.
- conditions: 테이블 및 342개 **미추출 대기 행만 있음**. 실제 AI 추출 JSON은 제공되지 않아 `condition_json=NULL`, `extraction_status=not_extracted`.
- **실제 RAG 검색, 사용자 조건 추출, 판정 및 근거 검증은 미연동.** DB/API 조회 시 데이터가 있다고 해서 추천 결과가 완성된 것은 아닙니다.
- SQLite 파일은 재현 가능한 로컬 데모. 실제 서버에서는 PostgreSQL JSONB 권장. 배포·보안 점검은 별도.

## Windows + VS Code 실행 (PowerShell)

```powershell
cd startup_support_backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# zip에는 이미 로컬 DB가 포함되어 있습니다. 재구축은 아래 2개 명령으로 합니다.
python -m scripts.ingest
python -m uvicorn app.main:app --reload --port 8000
```

열어볼 주소:

- http://localhost:8000/docs — API 문서/테스트 UI
- http://localhost:8000/health — 연결 확인
- http://localhost:8000/api/v1/announcements?limit=5 — 목록

마이그레이션이 필요한 **새 빈 DB**라면 먼저 `alembic upgrade head`를 실행하세요. ZIP에 포함된 SQLite 파일은 이미 해당 마이그레이션을 적용했습니다.

**정상 동작 확인:** `python -m pytest -q` → 작성된 테스트 6개 통과.

**참고:** Windows에서 가상환경 실행 정책 오류가 나면 VS Code 터미널에서 `cmd`를 사용하거나, 가상환경의 `python.exe`를 직접 호출해도 됩니다.

## 데이터 적재

`python -m scripts.ingest`는 `data/selected_342.csv`, `data/extract_report.csv`, `data/texts/*.txt`를 읽습니다. 여러 번 실행해도 같은 공고·파일이 중복으로 증가하지 않습니다. 원본 API 필드 21개를 `announcements.raw_fields` JSON에 보존합니다.

AI팀이 자격 조건 JSON을 제공하면:

```powershell
python -m scripts.ingest --conditions "C:\path\to\conditions.json"
```

허용 형식: JSON 객체 1개, JSON 객체 배열, `{"results":[...]}`, JSONL(한 줄에 하나). `공고ID`, `스키마버전`, 주요 필드, 상태값 형식을 검증합니다. **세부 하위 필드의 완전한 의미 검증이나 원문 근거 검증은 아직 하지 않습니다.** 팀원이 제공하는 최신 `스키마.md` 원본으로 강화해야 합니다.

`condition_json`은 전체를 저장하고, 시도/사업자등록/최대업력/최대나이만 안전한 경우 보조 컬럼으로 복사합니다. `대안조건` 또는 `트랙`이 있으면 단일값 필터에 오해가 생길 수 있으므로 보조 컬럼을 모두 NULL로 남깁니다. `NULL`은 추출 실패/없음/불명확의 판정 대용이 아닙니다.

## 주요 파일

- `app/db.py`: DB 연결(SQLAlchemy)
- `app/models.py`: ERD에 대응하는 4개 테이블
- `app/condition_utils.py`: 조건 JSON 기본 검증과 보조 컬럼 추출
- `scripts/ingest.py`: 재실행 가능한 CSV·텍스트·조건 JSON 적재기
- `app/main.py`: 조회 API 및 미구현 추천 API
- `app/schemas.py`: API 요청·응답 데이터 모델
- `migrations/`: Alembic 최초 DB 테이블 생성
- `tests/`: 요청 검증·재적재·FK·필터 오해 방지 테스트
- `docs/API_CONTRACT.md`: 프론트 연동 입출력 계약
- `docs/HANDOFF.md`: 팀원별 전달 사항
- `docs/ERD.md`: 데이터 설계·확장 방향
- `data/startup_support.db`: 실제 342건 데이터가 들어간 **로컬 SQLite DB**

## 기존 React/Vite 프로젝트 연결 방법

프론트 `src/services/supportMatch/client.ts`는 `POST /api/support-match`를 호출합니다. 아직 AI 검색/판정 연결 전이므로 이 경로는 **HTTP 409 + `INDEX_MISSING`**를 반환합니다. (기존 프론트는 404 또는 5xx를 받으면 샘플 데이터를 띄우므로, 가짜 신청 가능 결과를 막기 위해 409 사용.)

FastAPI의 실제 공고 조회 API는 `/api/v1/announcements`입니다. 기존 UI가 바로 이 경로를 사용하고 있지는 않아서 **프론트에 호출 코드를 추가하거나 어댑터 구현 필요**합니다. `docs/API_CONTRACT.md`를 프론트 담당자와 먼저 합의하세요.

Vite 개발환경에서 로컬 API를 호출하려면 프론트의 `vite.config.ts`의 프록시를 `http://localhost:8000`으로 설정해야 합니다. 이 ZIP은 프론트 코드를 직접 수정하지 않았습니다.

## 팀 데이터 취급 및 오해 방지

- 첨부 PDF/HWP에서 추출한 **텍스트**만 포함. PDF/HWP 파일 자체를 다운로드했다고 표시하지 않습니다.
- 다운로드 URL이 `/getImageFile.do?...` 같은 형태라서 URL 확장자가 아니라 **파일명**에서 확장자를 추출합니다.
- 첨부파일 여러 개는 기업마당 CSV에서 `@`로 이어져 있어 분리 저장합니다.
- 기간이 `예산 소진시까지`/`상시 접수`라면 원문 문자열을 보존하고 날짜는 NULL로 둡니다. 마감 상태나 지원 가능 여부를 임의 확정하지 않습니다.
- 프론트가 말하는 `eligibility` TS 규칙과 AI팀 v0.4 전체 JSON은 **서로 다른 구조**입니다. 정확한 변환기 및 판정 엔진 합의 전 임의로 연결하지 마세요.
- 백엔드 코드, 평가용 가상 사용자 데이터, 운영 사용자 데이터는 구분하고, 실제 사용자 개인정보 저장 시 보안정책을 별도 설계해야 합니다.
