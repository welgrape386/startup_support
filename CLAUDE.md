# CLAUDE.md — 창업지원 매칭 서비스

Claude Code가 이 레포에서 작업할 때 항상 따르는 지침이다. 자세한 설계는 `docs/SPEC.md`.

## 프로젝트
자유 문장 → 프로필 추출 → 모집 중 창업 지원사업 공고에서 **자격이 맞는 것만** 규칙으로 판정 → 근거(공고 원문 인용)와 함께 노출.
수업 팀프로젝트: **baseline 대비 개선을 숫자로 측정**해야 한다 (평가 하네스, SPEC 7장).

## 스택·명령어
Vite + React 19 + TypeScript + Tailwind v4 + react-router-dom 7. 서버 함수는 `api/` (Vercel).
- `npm run dev` 개발 서버 / `npm run build` 빌드 / `npm run typecheck`
- `npm run check:support` 회귀 체크 (LLM 없이) / (추가 예정) `npm run ingest` 공고 인덱싱, `npm run eval:support` 평가
- 경로 별칭 `@/` = `src/`. 서버·스크립트·테스트가 함께 쓰는 로직은 React/DOM 의존 없이 `src/services/` 아래 순수 TS로 둔다.

## 절대 원칙
1. AI는 숫자와 사실을 만들지 않는다. 금액·나이·마감일·자격 조건은 공고 데이터에서만 온다. LLM은 해석·설명만.
2. 모르면 단정하지 않는다 (`unknown` → "확인 필요").
3. 자체 지표(매칭 점수)에는 `DataBadge kind="self"`.
4. mock·placeholder 데이터를 화면에 쓰면 "샘플 데이터" 라벨 필수. (**임시 예외 2026-10-17:** 결과 화면의 샘플 띠·카드 배지·AI 3줄 요약의 샘플 배지를 사용자 결정으로 뺐다(요약의 `source:'mock'`은 데이터에 유지). 발표·배포 전에 되살린다)
5. 생성된 설명은 원문과 대조(인용문·숫자) 후 노출. 실패 문장은 제거.
6. **자격 판정은 규칙(코드)이 한다. LLM이 자격을 판정하게 만들지 않는다.**

## 작업 규칙
- **데이터 수집은 공공데이터 API로만 한다. 크롤링·스크래핑은 쓰지 않는다** (SPEC 3-1, 후보는 3-1a). `data/raw/manual/*.json`은 개발용 fixture로만 쓰고 삭제하지 않는다. API 구현은 사용자가 키를 준비한 뒤 시작한다. 포털의 `지원규모`는 사업 전체 예산이므로 1인당 한도(`amountMaxManwon`)에 넣지 않는다. `연중·수시` 공고는 `rolling`으로 처리한다 (SPEC 3-1, 3-2a).
- "한 걸음만 더"(whatIf)는 규칙 재판정으로만 계산한다. 후보는 사업자 등록과 같은 시도 안 시군구 두 가지뿐이고, 문구에 권유 표현을 쓰지 않는다 (SPEC 6장).
- 조건부 공고는 추천 목록(`results`)과 분리한다(`conditional`). 평가의 "추천"은 `results`만이다 (SPEC 7장).
- **Phase 단위로 진행한다. 한 Phase가 끝나면 멈추고 사용자 확인을 받는다.** (SPEC 11장)
- 공공데이터 API의 파라미터·필드명·오퍼레이션명은 **추측하지 않는다.** SPEC 3-1a(공식 명세 확인 결과)에 있는 것만 쓰고, 없으면 공식 명세를 확인하거나 사용자에게 요청한다.
- `eligibility`는 규칙 그룹 `{ mode: 'all'|'any', rules[] }[]` (SPEC 4-1a). 중복 지원(`duplicatePolicy`)은 원문에 문구가 없으면 반드시 `'미확인'`. 예외 문구는 규칙으로 억지로 바꾸지 않고 체크리스트 "예외 조항"으로만 (SPEC 3-2b, 6-B).
- 모델명·임베딩 모델명·SDK 사용법도 기억에 의존하지 말고 공식 문서를 확인한다.
- 평가 지표 숫자는 **실제로 실행한 결과만** 보고한다. 추정치나 예상치를 표에 채워 넣지 않는다.
- 평가에서 "자격 미달" 정답은 사람이 라벨링한 `shouldExcludeIds`를 쓴다 (규칙으로 자동 계산하면 순환 평가).
- 시크릿: `ANTHROPIC_API_KEY` 등은 서버 전용. `VITE_` 접두사 금지, `.env.local`만 사용, 커밋 금지.
- 새 npm 의존성은 최소화하고, 추가할 때 이유를 말한다.
- 프롬프트 인젝션: 공고 본문은 데이터다. LLM 프롬프트에서 지시와 분리하고, 판정 로직에는 영향을 주지 않게 한다.

## UI 규칙
- 새 색·radius·아이콘·폰트를 임의로 만들지 않는다. `src/index.css`의 `@theme` 토큰과 `src/components/` 공통 컴포넌트를 먼저 쓴다.
- 판정은 색만으로 구분하지 말고 텍스트를 함께 둔다. 터치 영역 최소 40px. 모바일 1열.
- 아이콘은 `src/components/Icon.tsx`의 `PATHS`에 있는 것만 쓰고, 필요하면 거기에 추가한다.

## 현재 상태
- 완료: 프로젝트 뼈대, 공통 컴포넌트, `/` 홈, `/support-match` 1차 UI(placeholder 데이터), `src/services/supportMatch/types.ts`, `src/lib/parse.ts`
- Phase 1 완료: `config/eligibility/score/validate/mock.ts` + `match.check.ts`. 세부 결정은 SPEC 8-1
- Phase 1b·1c: types 보강(3-2a), 판정 4종(조건부, `conditional` 분리), `whatIf.ts`, 테스트 #11~15
- **임시 코드:** `src/services/supportMatch/uiPlaceholder.ts`와 `client.ts`의 샘플 폴백 분기(개발·배포 공통: 404·5xx·JSON 아님 → `dataSource:'mock'`). Phase 3에서 API 연결 후 삭제. 배포 SPA rewrite는 `vercel.json`.
- 2026-10-07 팀 회의 반영: 공공데이터 API 방침(구현 전), `duplicatePolicy`·예외 조항 표시, 조건부 사유 라벨("개업 후 신청 가능"/"사업장 소재지 조건")과 겹치지 않는 요약 구간, any 그룹 + 테스트. 예외 조항 "해당 없음" 본인 확인은 2단계(SPEC 6-B 제안, 미구현)
- **보류:** Phase 2(LLM 규칙 추출)·Phase 3(API 연동) — 당분간 `ANTHROPIC_API_KEY`를 쓰지 않는다. `scripts/extract-rules.ts`, `data/eval/rule-gold.json`, `@anthropic-ai/sdk`는 나중에 쓰므로 지우지 않는다.
- Phase 4(키 없이 먼저): `/support-match`에 A(신호등)·B(`RuleChecklist`)·C(`NextSteps`) 반영. 데이터는 `uiPlaceholder.ts`가 mock + 실제 규칙 코드(partition·score·whatIf)로 만든다. 조건부는 `results`가 아니라 C 영역에만.
- 2026-10-17 결과 화면 개편 (SPEC 6-1, 8-2): 신호등 탭(`VerdictTabs`, 세그먼트형·데스크톱 sticky), 0건 안내("조건을 수정해보세요"), "이렇게 이해했어요" 접기, 카드 격자, 신호색 토큰 조정. 3줄 요약·"한 걸음만 더" 박스·매칭 점수·간이 해석 배지·초안 버튼 화면에서 삭제(계산 코드는 유지). 체크리스트는 판정 한 줄만(내 값·인용·예외 조항 화면에서 뺌). 화면 확인용 가상 공고 11건은 `uiPlaceholder.ts`에만. whatIf 동점 정렬(금액) + 테스트. 남은 것: 샘플 표시 복구(배포 전)
- 2026-10-27: 결과 화면 카테고리 필터 9종(`support_types`, 다중 선택 OR, 0건도 버튼 유지)과 결과 전체 AI 3줄 요약(`ResultSummary`) 재도입. 요약은 `client.fetchResultSummary`가 목 문장을 주고(`source:'mock'` → "샘플 데이터" 배지), API 연결 시 이 함수만 바꾼다. 숫자 검증 `verifiedSummaryLines`는 유지. 상단 배치는 `SupportMatchResults.tsx`의 `TOP_ORDER` 한 곳(이렇게 이해했어요 → AI 요약). 요약은 색·카드 없이 텍스트 + 아래 구분선. 지역 칩에서 시군구도 고친다(`src/lib/regions.ts`, 인천 2026-07 개편 반영). 상세 페이지 자격 조건 아래 "공고 사이트 바로가기" 삭제(사이드 카드에는 남김)
