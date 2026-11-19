# 사용자 자연어 추출

사용자 문장 하나 -> 프로필 12칸 + 되묻기_유도 -> RAG 검색 · 판정

```
[입력 중]  문장 -> 규칙 -> 인식된 정보 / 빠진 정보    (API X)
[제출]     문장 -> 규칙 -> LLM 1번 -> 코드로 합치기 -> 프로필 -> 검색 / 판정
```

## 파일

| 파일 | 내용 |
| --- | --- |
| `user_extract.py` | 백엔드가 부르는 파일 |
| `extract_rules.py` | 규칙 (나이 · 지역 · 단계 · 업력 · 사업자 형태 · 성별 · 특수자격) |
| `extract_llm.py` | 규칙 + LLM (업종 · industry · need) |
| `data/` | 서울 동 -> 구, 서울 밖 시군구 (법정동 · 행정동 코드표) |
| `.env.example` | `.env`로 복사해서 `OPENAI_API_KEY` 넣기 |
| `추출_출력_예시.json` | `extract()` 출력 예시 (DB 컬럼 이름) |
| `판정입력_예시_U01_U10.json` | 판정에 넘기는 값 예시 |
| `eval/` | 정답셋 (148문장), 추출 결과, 채점 (`score.py`) |

## 쓰는 법

```python
from user_extract import extract, extract_quick, to_search_args, to_judge_profile, ASK_TEXT
from search_service import search          # rag/

p = extract_quick(text)                                   # 입력 중 (규칙만)
missing = [ASK_TEXT[a] for a in (p["ask_fields"] or [])]

row = extract(text)                                   # 제출할 때 (규칙 + LLM)
results = search(**to_search_args(text, row))
judge_in = to_judge_profile(row)
```

- 출력 키 = DB 컬럼 이름 (input_text, age, res_sido … ask_fields). 키는 항상 다 있고 빈 값은 null
- 판정에는 `to_judge_profile`이 users_v2 한국어 키 10칸 + industry + need로 바꿔서 넘김 (need는 B1이 씀)
- `.env`에 키가 없거나 LLM이 실패하면 규칙 결과만 줌
- 모델 gpt-4.1-mini, 1번에 약 1.2초, 제출 1,000번에 약 $1.3
- 패키지 : `openai`, `python-dotenv`

## 채점

```
cd eval
python score.py 사용자추출_정답셋_전체148.csv       # 규칙만
python score.py 사용자추출_정답셋_전체148.csv llm   # 규칙 + LLM (148번 호출)
```

| 셋 | 개수 | 쓰임 |
| --- | --- | --- |
| 정답셋 | 52 (RAG 질문 28 + 판정 사용자 10 + 신규 14) | 보면서 고침 |
| 검증셋 v1 · v2 · v3 | 20 · 20 · 28 | 보면서 고침 |
| 검증셋 v4 | 28 | 최종 점수 (정답 먼저 달고 안 고친 채 1번만) |

- `사용자추출_정답셋_전체148.csv` : 위 셋 전부 ("셋" 칸으로 구분)
- `추출결과_148.csv` : 같은 문장을 추출한 결과 (정답셋이랑 같은 칸 모양)

## 결과 (11/18)

| | 다 맞은 문장 |
| --- | --- |
| 검증셋 v4 (처음 보는 28문장) | 규칙만 5/28 -> 규칙 + LLM **22/28 (79%)** |
| 전체 148문장 (최종 코드) | 규칙만 85/148 -> 규칙 + LLM **133/148 (90%)**, 되묻기_유도 145/148 |

- 나이 · 거주지 · 단계 · 사업장 · 업력 · 사업자 형태 · 성별 · 특수자격 148/148
- 추출값으로 RAG 검색해도 사람이 적은 값이랑 점수 같음 (R@20 0.977 -> 0.986)
- 남은 오류 : 애매한 업종 (피트니스 · 세차장 -> 기타 등)
