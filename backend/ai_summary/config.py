"""설정값과 문장 틀. 숫자·문구를 바꿀 때는 이 파일만 고친다."""

import os

# 평가(STAGE 1~3)를 통과한 모델. 백엔드 .env의 OPENAI_MODEL(사용자 추출용)과 섞이지 않게 이름을 따로 둔다
MODEL = os.environ.get("AI_SUMMARY_MODEL", "gpt-4.1-mini")
TEMPERATURE = 0
MAX_TOKENS = 100

PROMPT_VERSION = "v7"   # 평가를 통과한 프롬프트 (prompts/benefit_v7.txt)
SERVER_VERSION = "s2"   # 끝 '지원' 제거, 억 단위·핵심어 개수 확인
MAX_LEN = 24            # 줄인 혜택 글자 수 상한 (공백 포함)
TOP_N = 3               # payload의 top_green에 넣을 공고 수

# ---- 문장 틀 ----
L1 = "지금 신청 가능 {g}개, 조건 변경 시 가능 {y}개, 판단 어려운 공고 {w}개예요."
L2_GREEN = "추천 공고는 '{title}'{euro} {benefit}{eul} 지원해요."
L2_YELLOW = "조건 변경 시 신청 가능한 공고가 {y}건이 있으니 상세 내용을 확인해보세요."
L2_WHITE = "판단하기 어려운 공고가 {w}개 있어요. 조건 더 입력하면 정확도 올라가요."
L2_NONE = "추천할 만한 공고를 찾지 못했어요."
L3 = "'{title}'{iga} {when} {tail}"

# ---- 추천 순서 ③에서 '뒤로 보내는' 지원유형 (지원유형_연결표의 유형 이름) ----
CONSULT_TYPES = {"컨설팅·상담", "교육", "법률"}
