# 사용자 자연어 추출

사용자 문장 하나 -> 프로필 12칸 + 빠진 정보 -> RAG 검색 · 판정

```
[입력 중]  문장 -> 규칙 -> 인식된 정보 / 빠진 정보    (API X)
[제출]     문장 -> 규칙 -> LLM 1번 -> 합치기 -> 프로필 -> 검색 / 판정
```

## 쓰는 법

```python
from user_extract import extract, extract_quick, to_search_args, to_judge_profile, ASK_TEXT

p = extract_quick(text)                                   # 입력 중 (규칙만)
missing = [ASK_TEXT[a] for a in (p["ask_fields"] or [])]

row = extract(text)                                       # 제출할 때 (규칙 + LLM)
search_args = to_search_args(text, row)                   # RAG search() 인자
judge_in = to_judge_profile(row)                          # 판정 입력
```

- 출력 키 = DB 컬럼 이름 (`input_text`, `age`, `res_sido` … `ask_fields`). 빈 값은 null
- `.env`에 `OPENAI_API_KEY`가 없거나 LLM이 실패하면 규칙 결과만 줌
- 모델 gpt-4.1-mini, 패키지 : `openai`, `python-dotenv`

## 파일

| 파일 | 내용 |
| --- | --- |
| `user_extract.py` | 백엔드가 부르는 파일 |
| `extract_rules.py` | 규칙 (나이 · 지역 · 단계 · 업력 · 사업자 형태 · 성별 · 특수자격) |
| `extract_llm.py` | 규칙 + LLM (업종 · industry · need) |
| `data/` | 서울 동 -> 구, 서울 밖 시군구 (법정동 · 행정동 코드표) |
| `.env.example` | `.env`로 복사해서 `OPENAI_API_KEY` 넣기 |
| `추출_출력_예시.json` | `extract()` 출력 예시 |
| `판정입력_예시_U01_U10.json` | `to_judge_profile()` 출력 예시 |
| `eval/score.py` | 채점 (`python score.py 사용자추출_정답셋_전체148.csv`, 뒤에 `llm` 붙이면 LLM까지) |
| `eval/사용자추출_정답셋_전체148.csv` | 정답셋 148문장 ("셋" 칸으로 구분) |
| `eval/추출결과_148.csv` | 같은 문장 추출 결과 |
