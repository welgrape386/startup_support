# AI 3줄 요약 연결 요청 (ai_summary 파트)

`feature/AI-summary` 브랜치에는 **`backend/ai_summary/` 새 폴더만** 있습니다. 기존 파일은 하나도 안 건드려서 머지해도 충돌이 없습니다.
폴더를 머지한 뒤 아래 **백엔드 2줄 + 프론트 7줄**만 넣어 주세요.

## 1. 백엔드: `backend/app/main.py` (2줄)

`support_match()` 함수 안, `payload = get_match_response(...)` 바로 다음에 추가

```python
    payload = get_match_response(request, session, extracted=extracted)   # 원래 있는 줄

    from ai_summary import attach_ai_summary          # ← 추가
    attach_ai_summary(payload, extracted)             # ← 추가
```

- 응답에 `aiSummary: {"lines": [...]}` (문자열 1~3개)가 추가됩니다. 기존 필드는 그대로예요.
- 필요한 값은 전부 `payload`에서 읽습니다: 결과별 `signal`, `program.id/title/applyEnd`, `coverage.asOf`(=JUDGE_AS_OF)
- `local_demo.py`는 수정할 필요 없습니다.
- 안에서 어떤 오류가 나도 예외를 던지지 않고 `lines: []`가 됩니다 → 매칭 응답은 항상 정상

## 2. 프론트

### `src/services/supportMatch/types.ts` — `SupportMatchResponse` 안, `coverage: Coverage` 다음 (2줄)

```ts
  /** AI 3줄 요약 (백엔드 ai_summary 파트). 없거나 빈 배열이면 샘플 문장을 쓴다 */
  aiSummary?: { lines: string[] }
```

### `src/services/supportMatch/client.ts` — `fetchResultSummary` 안 첫 줄에 (5줄)

```ts
export async function fetchResultSummary(res: SupportMatchResponse): Promise<{ lines: string[]; source: 'ai' | 'mock' }> {
  // 백엔드 AI 요약이 있으면 그대로 쓴다. 숫자 검증(verifiedSummaryLines)은 건너뛴다:
  // 문장 숫자는 서버가 판정 건수·공고 데이터에서 넣은 값이고, 공고명 속 숫자(2026년, 5차)·혜택 숫자(50~80%)까지 검사하면 정상 문장이 버려진다
  const ai = res.aiSummary?.lines
  if (ai && ai.length) return { lines: ai.slice(0, 3), source: 'ai' }
  return { lines: verifiedSummaryLines(mockSummaryLines(res), res), source: 'mock' }   // 원래 있는 줄
}
```

## 3. 환경변수 (선택)

`OPENAI_API_KEY`는 기존 키를 같이 씁니다. 아래는 안 넣어도 기본값으로 동작해요.

```
AI_SUMMARY_MODEL=gpt-4.1-mini   # 평가 통과 모델 (OPENAI_MODEL은 사용자 추출용이라 따로 둠)
AI_SUMMARY_LLM=on               # off면 LLM 없이 혜택 원문 첫 항목으로 문장 생성
```

- Render에서는 `ENABLE_PUBLIC_LLM=true`일 때만 LLM 호출 (사용자 추출과 같은 규칙)
- 패키지 `openai`, `python-dotenv`는 이미 `backend/requirements.txt`에 있음

## 4. 확인

```bash
cd backend
python -m pytest -q ai_summary/tests                  # 84개 통과 (API 호출 없음)
python -m uvicorn app.main:app --reload --port 8000   # POST /api/support-match → aiSummary.lines
```

출력 예

```
지금 신청 가능 1개, 조건 변경 시 가능 8개, 판단 어려운 공고 9개예요.
추천 공고는 '2026년 비즈니스지원단(현장클리닉) 사업 운영계획 공고'로 전문상담을 지원해요.
```

## 5. 같이 정해 주세요

- **검색 후보를 최종 62건으로 제한할지**: 지금은 342건 전체를 검색해 62건 밖 공고가 ⚪로 섞이고, 1줄의 "판단 어려운 공고 N개"가 그만큼 늘어납니다.
- **프론트 숫자 검증 건너뛰기**: 위 client.ts 주석 이유로 AI 요약에는 검증을 건너뛰게 했습니다.
