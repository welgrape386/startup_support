# 자격 판정 (judgment)

사용자 정보와 공고 자격 조건을 비교해 신청 가능 여부를 신호등으로 판정하고, 사유와 원문 근거 문장을 함께 제시한다.

판정 방법은 다음 세 가지를 비교했다.

| 방법 | 내용 |
|---|---|
| B0 | 공고 API 칸만 보고 필터링 |
| B1 | LLM이 공고 원문을 읽고 직접 판정 |
| 제안 | LLM은 원문에서 자격 조건만 추출하고, 판정은 규칙 코드(`rule_judge.py`)가 한다 |

## 폴더 구조

**goldset/                      정답셋**
- `gold_announcements_v3.csv`: 평가 공고 30건
- `users_v2.csv`: 사용자 샘플 10명 (U01~U10)
- `users_proposal3.csv`: 사용자 추출 결과 (제안-3 입력)
- `judge_gold_v2.csv`: 판정 정답 300쌍 (사용자 × 공고, 근거 문장·사유 포함)

**texts_gold30/                 공고 원문 30건 (근거 검증용)**

**b0/                           B0: API 칸 필터**
- `b0_api_filter.py`: B0 측정 코드
- `api_fields.csv`: 공고 API 칸 값
- `pred_B0.csv`: 판정 결과

**b1/                           B1: LLM 직접 판정**
- `b1_llm_judge.py`: B1 측정 코드
- `b1_prompt_v1.md`: 판정 프롬프트
- `results/`: 판정 결과

**proposal/                     제안: 조건 추출 + 규칙 판정**
- `rule_judge.py`: 판정 코드
- `conds_gold30/`: 공고 조건 JSON (사람이 검수한 정답)
- `conds_llm_v4/`: 공고 조건 JSON (LLM 추출 그대로)
- `업종_사전.csv`: 공고 업종명 → 업종 카테고리
- `industry_map.csv`: 공고·트랙별 허용/제외 업종 카테고리
- `ann_dates.csv`: 공고일·접수마감일
- `results/`
    - `judge_p1_gold_v1/`:       제안-1 (정답 오류 수정 전)
    - `judge_p1_gold_v2/`:       제안-1 정답 조건으로 판정
    - `judge_p2_llm/`:           제안-2 LLM 추출 조건으로 판정
    - `judge_p3/`:               제안-3 사용자 추출 결과 + LLM 추출 조건으로 판정


결과 폴더마다 `_pred.csv`(쌍별 판정), `_detail.json`(조건별 결과), `_metrics.json`(지표)이 들어 있다.