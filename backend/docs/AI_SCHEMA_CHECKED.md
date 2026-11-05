# 스키마 v0.4 더블체크 수정본 (AI 사용자 자연어 추출)

## 결론
- 사용자 `Schema`의 **4절 사용자 프로필 18개 필드명**과 `user_extraction/schema.py`가 정확히 일치함.
- **공고 조건 추출**을 다루는 `추출가이드`의 `상태/근거/트랙`은 사용자 JSON에 섞지 않음.
- 독립형 AI 추출 모듈 유지. 현재 백엔드는 변경하지 않음.

## 무엇을 수정했나?
1. `user_extraction/demo_rules.py`: 창업 **예정** 표현과 이미 운영 중인 표현을 구별. 미래 법인 설립을 현재 법인으로 오인하지 않음. `사업자등록 전`은 현재 `미등록`을 의미할 뿐, 과거 사업자이력이 `없음`이라는 증거는 아니므로 이력은 `null`. 과거 폐업을 말하면 `폐업`을 우선. Q02의 '창업자금 모집'은 CSV 평가 기준대로 **검색 보조용 추론 단계**에만 `예비`로 기록하고, 사업자이력을 만들어내지 않음.
2. `user_extraction/extraction_prompt.txt`: 위 규칙을 실제 LLM 프롬프트에도 명시.
3. `tests/test_extractor.py`: 스키마 필드명 + 충돌 사례 등 10개 테스트 추가(총 **32개**).
4. `evaluate.py`: 요청에 따라 `difficulty`와 `size`를 사용자 추출 정확도에서 제외. `need/age/region/stage/biz_months/biz_type/gender/industry/fund` **9개** 평가.

## 로컬 실행 (Windows PowerShell)
AI 프로젝트의 최상위 폴더에서:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe evaluate.py --mode demo --out-dir output_demo
```

결과 파일: `output_demo/test_results.csv`, `output_demo/report.json`, `output_demo/Q01.json` ~ `Q28.json`.

예시 문장 1건:

```powershell
.\.venv\Scripts\python.exe run_extract.py --mode demo --text "크라우드펀딩으로 창업 자금을 모아보고 싶어요." --out output_demo\Q02_manual.json
```

**실제 LLM 평가**: `.env.example` 참고하여 `.env`에 개인 API 키 설정 후:

```powershell
.\.venv\Scripts\python.exe evaluate.py --mode llm --out-dir output_llm
```

`demo` 결과 28개×9항목 = 252개 비교값 일치는 **규칙 기반 테스트셋 일치**이며 LLM 정확도 100%를 의미하지 않음. 실제 LLM 28개에 대한 정확도는 미측정. API 요금 발생 가능.

## 아직 팀과 추가로 확인할 것
- `보유요건`, `특수자격`, `제외해당`의 완전한 enum 목록은 이번 스키마 HTML에서 별도 링크(`항목별 정의`, 스키마 3절)로 되어 있어 **링크 페이지 자료가 필요**. 현재 `schema.py`는 배열 타입만 검사함.
- `Schema 4절`의 일부 항목에 명시적 `null` 허용이 적혀 있지 않지만, `search_questions.csv` 요구사항은 **미언급 → null**. 현재 코드는 사용자 자연어의 정보 미언급을 우선해 허용함. 자격판정 담당자와 최종 합의 필요.
- Q02 `stage=예비`는 원문상 미등록 확정이 아닌 **의도 추론**이므로 `사업자이력=null`을 유지.
- `추출가이드`의 지역 명칭 일부는 공고 조건 추출 세부 규칙에 속하므로 사용자용 전국 주소정규화 범위는 추가 논의 가능.

## 적용 위치
이 ZIP은 **독립 AI 모듈 전체 실행본**. 원래 작업하던 폴더를 백업하고 새 폴더로 열거나, 별도 작은 패치 ZIP의 네 파일만 현재 AI 모듈에 복사해도 됨. **backend/** 폴더와는 별개. GitHub에 `.env`, `output_demo`, `output_llm`, `.venv`는 올리지 말 것.
