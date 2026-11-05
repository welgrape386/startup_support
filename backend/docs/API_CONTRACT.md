> ⚠️ **구 통합 설계 문서입니다.** 이 ZIP에는 8개 테이블을 구현한 코드와 로컬 검색 데모가 추가되었습니다. 현재 실제 상태는 [IMPLEMENTED_V2.md](IMPLEMENTED_V2.md)를 우선 참고하세요.

# API_CONTRACT.md — 프론트 ↔ 백엔드 입출력 계약 v2

> 현재 GitHub `welgrape386/startup_support`의 `src/services/supportMatch/types.ts`, `client.ts`, `SupportMatchResults.tsx`, `SupportMatchDetail.tsx`, `vite.config.ts` 확인 기준. **지금 FastAPI에 구현된 내용**과 **AI 연결 후 목표 계약**을 구별했습니다.

## 계약이란?

프론트(React)가 서버에 어떤 URL과 JSON을 보내며, 백엔드(FastAPI)는 어떤 상태 코드와 JSON 키/자료형으로 답하는지 합의한 규칙입니다. 데이터베이스 테이블 구조 그 자체가 아닙니다.

```text
[입력 화면 React]
    POST /api/support-match  {text, overrides?}
        ↓
[FastAPI] 사용자 조건 추출 → RAG 검색 → 판정
        ↓
[DB] announcements + conditions + texts 조회
        ↓
[FastAPI] FE의 SupportMatchResponse 형태로 조립
        ↓
[결과 화면] 신호등·추천·조건부·제외·요약
    클릭 → [상세 화면] 특정 공고·조건/근거 표시
```

## 1. 지금 실제로 구현된 API

| Method | 경로 | 화면/목적 | 현재 상태 |
|---|---|---|---|
| GET | `/health` | 개발 서버 확인 | 구현/테스트 |
| GET | `/api/v1/announcements?q=&category=&limit=20&offset=0` | 공고 목록 관리·조회 | 구현/테스트 |
| GET | `/api/v1/announcements/{announcement_id}` | 공고 상세 메타·첨부파일 | 구현/테스트 (프론트 미연결) |
| GET | `/api/v1/announcements/{announcement_id}/text` | 추출된 원문 및 오류 | 구현/테스트 |
| GET | `/api/v1/announcements/{announcement_id}/conditions` | 공고 조건 JSON·검색 컬럼 | 구현 (현재 실제 JSON 0건) |
| POST | `/api/support-match` | 사용자 입력→AI 추천 | **HTTP 409 INDEX_MISSING, AI 미연동** |

## 2. 프론트 현재 핵심 요청 (소스 그대로)

```ts
type SupportMatchRequest = {
  text: string
  overrides?: Partial<Record<keyof UserProfile, unknown>>
}
```

예시 요청 (`POST /api/support-match`, `Content-Type: application/json`):

```json
{
  "text": "서울 마포구에 거주하는 27세 예비창업자이고 카페 창업을 준비 중입니다.",
  "overrides": {
    "age": {"value": 27, "evidence": "사용자 직접 입력"}
  }
}
```

프론트 `config.ts`의 `MAX_TEXT_LENGTH=1000`; 입력 화면에서는 최소 10자 UI 검사가 있으나 API 입력 검증 기준과 분리해서 관리합니다. overrides의 값은 UserProfile의 해당 객체 구조/키를 기준으로 프론트와 합의합니다.

## 3. 프론트가 성공 시 요구하는 최상위 응답

```ts
SupportMatchResponse = {
  profile: UserProfile
  missing: (keyof UserProfile)[]
  results: MatchResult[]
  conditional: MatchResult[]
  excluded: {programId:string; title:string; failedReasons:string[]}[]
  nextSteps: NextStep[]
  summary: MatchSummary
  coverage: Coverage
  meta: {
    dataSource: 'live' | 'mock'
    parser: 'llm' | 'rule'
    indexBuiltAt: string
    totalPrograms: number
    droppedClaims: number
  }
}
```

**중요:** 이 타입에서 `results`는 자격 충족/확인 필요 후보, `conditional`은 별도 '한 걸음만 더', `excluded`는 자격 미달. 세 그룹을 임의로 하나로 합치면 현재 React 화면이 깨질 수 있습니다.

`MatchResult` 주요 필수 필드:

- `program`: `SupportProgram`에서 `eligibility`만 제외한 상세 공고 객체 (`id`,`source`,`sourceId`,`title`,`agency`,`supportTypes`,`rolling`,`status`,`duplicatePolicy`,`summary`,`url`,`fields`,`fetchedAt`,`reviewed` 등)
- `verdict`: `'자격 충족' | '확인 필요' | '조건부' | '자격 미달'`
- `score`: 숫자
- `rules`: `{rule, result:'pass'|'fail'|'unknown', reason, group?}[]`
- `headline`: 카드 제목/설명
- `reasons`, `cautions`: `{text,quote,chunkId}[]`
- `exceptions`: `{quote,section}[]`
- `daysLeft`: 숫자 또는 `null`

`profile`은 타입이 단순 사전이 아니며 `age`, `sido`, `sigungu`, `bizStage`, `industryCategory`, `industryText`, `fundingGapManwon` 등에서 `{value, evidence?}` 형태를 기대합니다. `targetGroups`, `needs`는 배열입니다. `summary`, `coverage`, `nextSteps`는 **원본 TS 타입을 그대로 구현**해야 하며 내용이 빈 객체 `{}`여서는 안 됩니다.

### 응답 구조 예시 (실제 판정값 아님)

아래 예시는 필드 간 데이터 흐름을 이해하는 **축약 도식**으로 실제 성공 응답으로 보내면 안 됩니다.

```json
{
  "profile": {"age":{"value":27,"evidence":"입력값"},"sido":{"value":"서울특별시"}},
  "missing": [],
  "results": [{"program":{"id":"PBLN_..."},"verdict":"자격 충족","score":84,"rules":[],"headline":"예시"}],
  "conditional": [],
  "excluded": [],
  "nextSteps": [],
  "summary": {"eligibleCount":1,"checkCount":0,"conditional":{"bizStage":0,"sigungu":0},"urgent":null,"caution":null},
  "coverage": {"sources":[{"portal":"기업마당","count":342}],"total":342,"asOf":"2026-10-24","regions":[]},
  "meta": {"dataSource":"live","parser":"llm","indexBuiltAt":"","totalPrograms":342,"droppedClaims":0}
}
```

**경고:** 위 축약 예시의 `profile`과 `program` 등에는 실제 TS 필수 키가 일부 생략돼 있습니다. 구현 및 자동 테스트에서 이 JSON을 그대로 성공 응답으로 사용하지 마세요.

## 4. 현재 실제 POST 응답

```http
HTTP/1.1 409 Conflict
Content-Type: application/json
```

```json
{"error":{"code":"INDEX_MISSING","message":"공고 검색·판정 AI가 아직 서버에 연결되지 않았습니다. 실제 추천 결과를 제공할 수 없습니다."}}
```

실제 AI 검색·판정이 연결되기 전에는 🟢 자격충족을 가짜로 반환하면 안 됩니다. `client.ts`는 HTTP 404/5xx 또는 비JSON이 오면 샘플 placeholder로 폴백할 수 있으므로 **실데이터 여부를 `meta.dataSource`로 확인**해야 합니다.

## 5. 상세 페이지 계약(연동 단계)

- 현재 `SupportMatchDetail.tsx`는 URL `id`와 React Router의 `location.state.result`를 함께 사용합니다. 직접 URL 입력/새로고침 시 `result`가 사라져 '공고를 찾을 수 없어요'가 나올 수 있습니다.
- 기존 구현된 `GET /api/v1/announcements/{id}`는 공고 메타와 첨부파일을 제공합니다.
- 상세 페이지가 `MatchResult`를 요구하는 영역(신호등/체크리스트/근거)은 공고 메타만으로 채울 수 없습니다. `GET /api/v1/match-runs/{run_id}/results/{announcement_id}` 또는 명시적인 조건부 조회/재판정 API 중 선택해야 합니다.
- 명세에 없는 지원금액/서류/우대사항은 **NULL 또는 미추출**로 노출하고 API에서 꾸며내지 말 것.

## 6. 프론트와 DB 필드 매핑 (예시)

| FE SupportProgram | DB 또는 계산 | 비고 |
|---|---|---|
| `id` | `announcements.announcement_id` | 문자열 ID |
| `source`, `sourceId` | `announcements.source`, `announcement_id` | 다중 포털 확대 시 ID 정책 재검토 |
| `title`, `agency`, `operator` | `announcements.title`, `agency`, `operator` | 메타 |
| `supportTypes` | `announcements.support_types_json` | 컬럼 아직 없음; 매핑 기준 필요 |
| `applyStart`, `applyEnd`, `rolling` | `announcements.apply_start`, `apply_end`, `rolling` | 기간 원문 보존 |
| `status` | `announcements.status` 또는 기준일 계산 | 아직 컬럼 없음; 비교 기준일 필요 |
| `eligibility` (프론트 RuleGroup) | `conditions.condition_json` → **변환 함수** | AI JSON v0.4와 TS 규칙은 형태 다름 |
| `duplicatePolicy` | `announcements.duplicate_policy_json` | 구분/근거/원문 확인 필요 |
| `attachmentFiles` | `files[]` | 파일 다운로드 완료와 링크 구분 |
| `submissionDocs`, `bonusPoints`, `rounds` | AI 안내정보 추출 후 JSON 또는 별도 테이블 | 당장 비어 있을 수 있음 |
| `fields` | `announcements.raw_fields` | 원본 출처/근거 검증 |
| `fetchedAt`, `reviewed` | `collected_at`, `reviewed` | 아직 별도 컬럼 추가 권장 |
| `reasons/cautions` | 판정 결과 + 검증된 원문 | UI 표시용 계산값 |
| `daysLeft` | apply_end/rolling + 응답 기준일 계산 | null 의미 주의 |

## 7. 개발 서버 연결

`vite.config.ts`의 `/api` 프록시는 현재 주석 처리이고 과거 Vercel 개발 서버 3000번을 가리킵니다. 프론트를 FastAPI에 붙일 때는 **별도 프론트 브랜치에서** 8000번으로 개발 프록시를 수정해야 합니다.

```ts
server: {
  proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } }
}
```

프론트는 `http://localhost:5173`, 백엔드는 `http://127.0.0.1:8000`에서 실행합니다. 기존 프론트 작성자 승인 없이 main을 직접 수정하지 않습니다.

## 8. 역할별 합의 포인트

- 프론트: 응답 JSON이 실제 `SupportMatchResponse` 전체 타입과 일치하는지 자동 타입/런타임 검사; 상세 URL 직접 접근 정책.
- 사용자 입력 AI: UserProfile `Extracted<T>` 구조와 최신 한국어 사용자 스키마 사이 변환 기준, 빈칸/미입력 처리.
- 조건 추출 AI: 스키마 v0.4의 실제 `conditions.json`, 증거 인용/검증 결과, 모델/버전 정보.
- 판정 AI: 네 가지 판정, 조건별 `pass/fail/unknown`, 트랙/대안조건, 근거/스코어 분리, false green 최소화.
- RAG: 반환 검색 후보와 `announcement_id`, `chunkId`, 점수의 계약. 검색 인덱스와 DB 간 키 일관성.
