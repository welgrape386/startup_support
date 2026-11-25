# RAG

### 01_원본
- `bizinfo_all_20261016_031038.csv` : 기업마당 공고 (10/16)
- `texts_v8_20261024/` : 공고 원문 텍스트

### 02_검색대상_시험지
- `make_docs.py` : 검색 대상 342건, 지역
- `make_category.py` : 지원 카테고리
- `make_industry.py` : 업종, 나이 조건
- `docs_snap1016.jsonl` : 검색 대상 공고
- `region_map.csv` : 공고별 지역
- `category_map.csv` : 공고별 지원 카테고리
- `industry_map.csv` : 공고별 업종
- `age_map.csv` : 공고별 나이 조건
- `업종_사전.csv` : 업종명 -> 업종 카테고리
- `*_check.csv` : 확인용

### 03_평가셋_문제+답안지
- `search_questions.csv` : 질문 28개
- `pool_snap1016.xlsx` : 답안지

### 04_실험_시험+채점결과
- `search_service.py` : 백엔드에서 부르는 검색
- `retrievers.py` : 검색 코드
- `eval_search.py` : 검색 채점
- `eval_elig.py` : 자격 문단 채점
- `build_emb.py`, `colab/` : 임베딩 만들기
- `cache/` : 임베딩
