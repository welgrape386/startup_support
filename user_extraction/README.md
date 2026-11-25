# 사용자 추출

- `user_extract.py` : 백엔드에서 부르는 파일
- `extract_rules.py` : 규칙 추출
- `extract_llm.py` : 규칙 + LLM 추출
- `.env.example` : API 키 넣는 칸
- `추출_출력_예시.json` : 추출 결과 예시
- `판정입력_예시_U01_U10.json` : 판정에 넘기는 값 예시

### data
- `dong_gu.csv` : 서울 동 -> 구
- `sigungu.csv` : 서울 밖 시군구

### eval
- `score.py` : 채점
- `사용자추출_정답셋_전체148.csv` : 정답셋 148문장
- `추출결과_148.csv` : 추출 결과
