# 2026-10-28 최신 프론트 API 계약 점검

**기준 프론트:** 사용자 첨부 `startup_support-main (1).zip`의 `src/services/supportMatch/types.ts`, `client.ts`, `SupportMatchResults.tsx`, `ProfileChips.tsx`.

## 1. 사용자 입력과 프로필 수정

프론트가 `POST /api/support-match`로 전송하는 JSON:

```json
{"text":"29살 서울 마포구에서 카페 창업을 준비 중이에요", "overrides":{"age":45,"sido":"서울특별시","sigungu":"종로구","bizStage":"기창업","industryCategory":"카페"}}
```

`overrides`는 **일부 키만 포함**할 수 있고, 서울에서 경기로 지역을 변경할 때 `sigungu:null`도 가능합니다. FastAPI는 변경한 나이를 기준으로 `targetGroups`를 재계산합니다. 입력하지 않은 값은 추측하지 않고 null을 유지해야 합니다.

## 2. 필수 결과 응답

`profile`, `missing`, `results`, `conditional`, `excluded`, `nextSteps`, `summary`, `coverage`, `meta`.

결과 카드 `results[].program`은 반드시 **`support_types`** 배열을 포함해야 합니다. 이 배열을 이용해서 프론트가 9개 카테고리 다중 선택 OR 필터를 적용합니다.

**9개 허용값:** 자금, 교육·컨설팅, 공간·시설, 홍보·판매, 인력, 기술개발, 해외진출, 제도·인증, 기타.

기존 `supportTypes`는 '융자', '보조금' 등의 다른 분류이며, 프론트의 새 카테고리 필터는 이것을 사용하지 않습니다. 두 필드의 의미를 섞지 않습니다.

## 3. API가 새로 필요한가?

이번 프론트에서 `POST /api/support-match`의 성공 응답 구조는 9개 카테고리 필드 외에 기존 계약과 양립합니다. **추가적인 백엔드 API는 필수는 아닙니다.**

새 `ResultSummary`는 `fetchResultSummary()`에서 *현재는 프론트 목 문장*을 만들어 반환하며, AI 3줄 요약 API는 아직 구현·호출되지 않았습니다. 로컬 통합본에서는 샘플임을 노출합니다. 이후 AI팀과 요약 입력·출력 포맷을 합의한 뒤 API를 별도로 연결할 수 있습니다.

## 4. 현재 테스트의 의미

FastAPI는 실제 DB의 342개 공고에서 지역 조건 및 키워드 관련도에 기반해 후보를 반환합니다. 이것은 RAG 검색도, 실제 신청자격 판정도 아닙니다. `verdict='확인 필요'`, `meta.dataSource='mock'`, `judgmentScore=null`이 현재 정상 상태입니다.

## 5. 추가 작업

- AI RAG/조건 판정 함수 연결 후 실제 `searchScore`와 `judgmentScore`를 수신·저장하고 응답에 반영
- 실제 AI 생성 3줄 요약의 입력/출력 및 검증 방식 합의
- 직접 링크/새로고침으로 상세 조회 가능하도록 상세 페이지를 ID 기반 API에 연결
- Render/PostgreSQL 배포 및 프론트 배포 URL 연동
