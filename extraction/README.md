# 공고 조건 추출 (extraction)

기업마당 지원사업 공고 원문에서 신청 자격 조건과 안내정보를 LLM으로 추출해 정해진 스키마의 JSON으로 만든다. 조건마다 원문 근거 문장을 함께 남겨, 판정 단계(`judgment`)가 이 JSON과 사용자 정보를 코드로 비교할 수 있게 한다.

- 대상: 서울·전국 공고 62건 (원문 텍스트는 범위 공고 342건 중 307건 추출)
- 모델: `gpt-6.1-terra` (Luna·Terra·Sol 세 모델을 같은 프롬프트로 비교해 선택)
- 담당: 정예은

## 처리 흐름

```
기업마당 API 수집 → 공고문 다운로드·텍스트 추출 → LLM 조건 추출 → 자동 검증(스키마·근거) → 사람 검토·수정 → 업종 후처리 → 서비스 데이터 62건
```

추출 방법은 다음 네 가지를 비교했다.

| 방법 | 내용 |
|---|---|
| B0 | 공고 API 칸 값만으로 조건을 만든다 (원문 안 읽음) |
| v1 | 스키마와 칸별 규칙을 담은 첫 프롬프트 |
| v3 | v2에서 자격이 아닌 내용(신청 절차, 서류 형식, 정산 규칙 등)을 뽑지 않도록 고치고, v3에서 기준일·본점 소재지·대안조건 규칙을 보완 |
| v4 (최종) | 대안조건 규칙 정리, 업종명 칸(`업종.업종명`) 추가 |

v2는 개발 15건에만 실행해서 아래 평가 표에는 없다. v3 → v4 변경 내용은 `prompts/extract_v4.md` 머리말에 있다.

## 결과

추출 정답셋 30건을 개발 15건과 평가 15건으로 나눴다. 프롬프트는 개발 15건만 보고 고쳤고, 아래 점수는 평가 15건에서 잰 것이다.

| 방법 | 판정 핵심 F1 | 전체 F1 | 전체 정밀도 | 업종명 F1 | 근거 일치율 |
|---|---|---|---|---|---|
| B0 | 0.50 | 0.23 | 0.85 | 0.00 | - |
| v1 | 0.87 | 0.73 | 0.60 | 0.00 | 98.5% |
| v3 | 0.89 | 0.80 | 0.71 | 0.00 | 100% |
| **v4** | **0.91** | **0.84** | **0.78** | **0.52** | **100%** |

- 공식 점수는 v4. 모든 점수는 최신 정답셋(`gold/extract_gold30_수정_업종확장/`) 기준이다
- 판정 핵심: 신청자 유형·사업자등록·업력·나이·지역·기업규모·창업이력 (판정 결과를 바로 바꾸는 칸)
- 근거 일치율: 추출한 근거 문장이 원문에 글자 그대로 있는 비율
- 업종명은 v4에서 새로 만든 칸이라 v1·v3는 0이다
- v3 → v4의 대안조건 규칙(`extract_v4.md` 1번)은 개발 15건(123842)을 근거로 고쳤지만, 같은 문제를 평가 15건(119801·119850)에서도 본 뒤에 넣었다. 이 때문에 v4 평가 점수에는 평가셋 정보가 조금 섞였을 수 있다
- 모델 선택 (v1, 개발셋, 판정 핵심 F1): Luna 0.89 / **Terra 0.95** / Sol 0.92. 개발 15건 중 119017은 정답셋에서 127031로 바뀌어 14건으로 계산

안내정보(v4, 평가 15건): 중복지원 1.00, 최대지원금 0.92, 지원규모 0.76, 제출서류 F1 0.97, 우대사항 F1 0.98, 모집일정 3/4

| 점수 | 근거 파일 |
|---|---|
| B0 | `results/b0_api_eval15/compare_gold.csv` |
| v1 | `results/extract_v1_eval_terra/compare_gold.csv` |
| v3 | `results/extract_v3_eval_terra/compare_gold.csv` |
| v4 | `results/extract_v4_eval_terra_업종확장/compare_gold.csv` |
| 모델 비교 | `results/extract_v1_dev_luna/`, `extract_v1_dev_terra/`, `extract_v1_dev_sol/` |
| 안내정보 | `results/info_v4_terra_후처리/score_info.csv` |

## 폴더 구조

**service_v4/                   자격조건 서비스 데이터 (최종, 11/19)**
- `공고_62/`: 공고마다 조건 JSON 1개
- `conditions_service_v4_업종확장.json`: 62건 합본 (백엔드·DB 적재용)
- `target_seoul_national_62.csv`: 공고ID·공고명·지역구분
- `업종명_목록.csv`: 공고별 허용·제외 업종명
- `출처.csv`: 공고별 출처 (정답셋 30건 / LLM 추출 32건 + 사람 수정)
- `공고목록_RAG8.csv`: 판정 2차 평가 공고 48건 목록
- `excluded_industries.csv`: 제외업종 표준 목록

**info_v4/                      안내정보 (최종, 11/18)**
- `공고_62/`, `info_62.json`: 공고별·합본 안내정보 (지원금, 지원규모, 제출서류, 우대사항, 모집일정 등)
- `지원내용_62.csv`: 지원내용 문구 (AI 3줄 요약 입력)

**handoff/판정평가_RAG48_20261124/   판정 2차 평가용 패키지**
- `LLM추출_48/`: 공고 48건 LLM 추출 조건 (사람 수정 전 원본)
- `원문_48/`: 공고 원문 텍스트
- `목록_48.csv`, `API필드_48.csv`: 공고 목록, API 칸 값

**prompts/                      프롬프트**
- `extract_v1.md` → `extract_v2.md` → `extract_v3.md` → `extract_v4.md`: 자격조건 추출 프롬프트 (v4가 최종). 파일마다 머리말에 앞 버전에서 바꾼 점과 그 이유(개발 15건에서 본 문제)가 있다. 모델에는 `## [프롬프트 본문]`부터만 보낸다
- `info_v4.md`: 안내정보 추출 프롬프트 (최종)
- `target_ids_gold30_v5.txt`, `_dev.txt`, `_eval.txt`: 정답셋 30건 / 개발 15건 / 평가 15건 공고ID (최신, `_v4`는 119017 → 127031 교체 전)
- `target_ids_info_*.txt`: 안내정보 개발·평가 공고ID
- `target_ids_seoul_national_62.txt`: 서비스 대상 62건 공고ID

**gold/                         정답셋**
- `extract_gold30_수정_업종확장/`: 자격조건 정답셋 30건 최신본
- `extract_gold30/`: 이전 버전
- `info_gold10/`: 안내정보 정답 (`info_라벨링.csv`, 평가 15건), 정답 만든 코드와 판단 기준(`info_헷갈리는기준.csv`)
- `README.md`: 정답셋 만든 과정, 공고 교체 기록

**results/                      실행·평가 결과**
- `b0_api_eval15/`, `extract_v1_eval_terra/`, `extract_v3_eval_terra/`, `extract_v4_eval_terra_업종확장/`: 평가 15건 결과와 정답 비교
- `extract_v1_dev_luna/`, `extract_v1_dev_terra/`, `extract_v1_dev_sol/`: 모델 비교 (v1, 개발 15건)
- `info_v4_terra_후처리/`: 안내정보 v4 결과와 채점 (`score_info.csv`)
- `manual_fixes.json`: 자격조건 LLM 추출 32건 검토 수정 기록 (칸, 바꾸기 전·후 값, 이유)
- `info_manual_fixes.json`: 안내정보 검토 수정 기록

결과 폴더 공통 파일: `compare_gold.csv`(정답 비교 점수), `compare_gold_diff.txt`(공고별 빠뜨린 것·더 뽑은 것), `evidence_check.csv`(근거 원문 대조), `schema_check.csv`(허용값 검사), `run_info.json`·`run_log.csv`(모델·설정, 공고별 토큰·비용)

**docs/                         문서**
- `스키마_최종.md`: 자격조건 스키마 (칸 정의, 허용값, 규칙)
- `안내정보_스키마.md`: 안내정보 스키마
- `추출가이드.md`: 칸별로 무엇을 뽑고 무엇을 안 뽑는지

**excluded/                     제외업종 표준 목록**
- `excluded_industries.csv`: 소상공인 정책자금 융자제외, 신용보증재단 보증제한, 창업지원법 제외 업종

**코드**

| 순서 | 파일 | 하는 일 |
|---|---|---|
| 1 | `fetch_bizinfo.py` | 기업마당 API로 공고 목록 받기 (키는 환경변수 `BIZINFO_KEY`) |
| 2 | `extract_texts.py` | 공고문 다운로드, PDF·HWP·HWPX·DOCX 텍스트 추출 |
| 3 | `run_extraction.py` | 프롬프트 + 원문으로 LLM 조건 추출 |
| 4 | `verify_extraction.py`, `evidence_rate.py` | 스키마·허용값 검사, 근거 문장 원문 대조 |
| 5 | `compare_gold.py` | 정답셋과 비교 (정밀도·재현율·F1) |
| 6 | `apply_fixes.py` | 사람 검토 수정 반영 |
| 7 | `add_industry_names.py`, `expand_industry_refs.py`, `make_industry_list.py` | 업종명 추가, 제외업종 목록 펼치기, 업종명 목록 만들기 |
| 8 | `build_service.py` | 서비스 데이터 62건 묶기 |
| - | `postprocess_info.py`, `verify_info.py`, `score_info.py` | 안내정보 후처리·검증·채점 |
| - | `b0_api_extract.py` | B0 (API 칸만으로 조건 만들기) |
| - | `make_review_sheet.py`, `make_judge_eval48.py` | 사람 검토표, 판정 2차 평가 패키지 만들기 |

## 실행 방법

```bash
cd extraction
pip install -r requirements.txt
cp .env.example .env        # 키 채우기
```

공고 원문 텍스트 307건은 main 브랜치 `backend/data/texts/`에 있다. 스크립트는 `extraction/output/texts/`에서 읽으므로 그 폴더로 복사한다 (또는 `fetch_bizinfo.py` → `extract_texts.py`로 다시 만든다).

```bash
# 평가 점수 다시 계산 (LLM 호출 없음, 키 불필요)
python compare_gold.py --gold gold/extract_gold30_수정_업종확장 results/b0_api_eval15 results/extract_v1_eval_terra results/extract_v3_eval_terra results/extract_v4_eval_terra_업종확장
python score_info.py results/info_v4_terra_후처리
python verify_extraction.py results/extract_v4_eval_terra_업종확장     # 근거 원문 대조 (output/texts 필요)

# 추출 다시 실행 (OPENAI_API_KEY 필요)
python run_extraction.py --prompt prompts/extract_v4.md --ids prompts/target_ids_gold30_v5_eval.txt --model gpt-6.1-terra --out results/새폴더
```

새 공고를 추가할 때: `run_extraction.py` → `verify_extraction.py` → 사람 검토 → `apply_fixes.py` → `expand_industry_refs.py` → `build_service.py`

## 참고

- 판정 정답셋(나주희)은 이 폴더에 없고, 추출할 때 모델에 넣지 않았다
- API 키(`.env`)는 올리지 않는다
