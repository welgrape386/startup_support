"""공고명 정리와 조사(을/를, 로/으로, 이/가) 고르기. LLM을 쓰지 않는 규칙 함수만 있다."""
import re


def clean_title(t: str) -> str:
    """문장에 넣을 공고명. 연도·차수는 남기고 아래만 지운다."""
    t = re.sub(r"^\[[^\]]*\]\s*", "", t)       # 맨 앞 [서울] 같은 지역 태그
    t = re.sub(r"\s*\([^()]*\)\s*$", "", t)     # 맨 끝 괄호 설명
    t = re.sub(r"\s\([^()]*\)", "", t)          # 띄어 쓴 괄호 = 별칭 (예: 창업대전 (Startup Water 2026))
    t = t.replace("(팀)", "")                   # 참가자(팀) → 참가자
    return re.sub(r"\s+", " ", t).strip()


# 숫자·영문은 읽는 소리로 받침을 정한다 ('' 받침 없음 / 'l' ㄹ받침 / 'o' 그 외 받침)
_DIGIT = {"0": "o", "1": "l", "2": "", "3": "o", "4": "", "5": "", "6": "o", "7": "l", "8": "l", "9": ""}
_LETTER = {"L": "l", "M": "o", "N": "o", "R": "l"}


def jong(text: str) -> str:
    t = re.sub(r"[\s\)\]\}'\"」』”’.,·]+$", "", text)
    if not t:
        return ""
    c = t[-1]
    if "가" <= c <= "힣":
        j = (ord(c) - 0xAC00) % 28
        return "" if j == 0 else ("l" if j == 8 else "o")
    if c.isdigit():
        return _DIGIT[c]
    if c == "%":
        return ""          # 퍼센트
    return _LETTER.get(c.upper(), "")


def eul(w: str) -> str:   # 을/를
    return "를" if jong(w) == "" else "을"


def euro(w: str) -> str:  # 로/으로
    return "로" if jong(w) in ("", "l") else "으로"


def iga(w: str) -> str:   # 이/가
    return "가" if jong(w) == "" else "이"
