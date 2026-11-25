# 지원-Fit RAG 검색

사용자 문장으로 공고를 찾아서 상위 20개를 판정으로 넘김. 공고마다 근거 문단도 같이 줌

## 쓰는 법

```python
import sys; sys.path.insert(0, "rag/04_실험_시험+채점결과")
from search_service import search
search("마포구에서 디저트 카페를 준비하는 예비창업자예요",
       user_gu="마포구", stage="예비창업", need="홍보·판매", industry_cat="음식·카페", age=29)
```

| 인자 | 값 |
| --- | --- |
| `user_gu` | 서울 구 이름 (예비창업 = 창업 예정 구, 초기창업 = 사업장 구). 모르면 빈칸 |
| `stage` | 예비창업 / 초기창업 |
| `need` | 원하는 지원 1~2개 (`홍보·판매\|인력`). 없으면 빈칸 |
| `industry_cat` | 업종 카테고리 1~2개 (`음식·카페\|도소매·판매`) |
| `age` | 만 나이 |

- 사용자 추출 결과 → 위 인자는 `to_search_args(text, row)`가 만들어줌
- 결과 형식은 `search_service.py` 맨 위에 있음. 처음 부를 때 모델(bge-m3)을 불러와서 수십 초 걸림
- 패키지 : `pandas numpy openpyxl rank_bm25 kiwipiepy sentence-transformers`

## 폴더

| 폴더 | 내용 |
| --- | --- |
| `01_원본/` | 기업마당 공고 1477건 (10/16), 원문 추출 307건. 수정 X |
| `02_검색대상_시험지/` | 검색 대상 공고, 지역 · 지원 카테고리 · 업종 · 나이 표 |
| `03_평가셋_문제+답안지/` | 질문 28개, 답안지 |
| `04_실험_시험+채점결과/` | 검색 코드, 채점 코드 |

### 02_검색대상_시험지

| 파일 | 내용 |
| --- | --- |
| `make_docs.py` → `docs_snap1016.jsonl`, `region_map.csv` | 검색 대상 342건, 공고별 지역 (서울 / 전국 / 타지역, 서울 구) |
| `make_category.py` → `category_map.csv` | 공고별 지원 카테고리 9개 |
| `make_industry.py` → `industry_map.csv`, `age_map.csv` | 조건 추출 JSON → 업종 카테고리, 나이 조건 |
| `업종_사전.csv` | 조건 추출 업종명 → 업종 카테고리 |
| `*_check.csv` | 눈으로 확인하는 표 (코드에서 안 씀) |

`make_industry.py`를 다시 돌리려면 조건 추출 `conditions_service_v4_업종확장.json`을 `00_참고자료/업종_v4/`에 넣기 (깃에 안 올림)

### 03_평가셋_문제+답안지

| 파일 | 내용 |
| --- | --- |
| `search_questions.csv` | 질문 28개 (유형 A 직접 / B 우회 / C 지역 / D 자격) + 질문별 사용자 값 |
| `pool_snap1016.xlsx` | 답안지 1049줄 (질문 × 공고 0 · 1 · 2점), 채점 규칙은 '채점기준' 시트 |

### 04_실험_시험+채점결과

| 파일 | 내용 |
| --- | --- |
| `search_service.py` | 백엔드가 부르는 검색 |
| `retrievers.py` | 검색 부품 (문단, 키워드 · 의미 검색, 지역 거르기, 순위 조정) |
| `eval_search.py` | 답안지로 채점 (버전별 비교) |
| `eval_elig.py` | 자격 문단 검색률 |
| `build_emb.py`, `colab/` | 원문 문단 임베딩 만들기 |
| `cache/emb_v2b_v8_passage500.npy` | 원문 문단 임베딩 |
