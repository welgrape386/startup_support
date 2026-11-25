"""
백엔드가 부르는 파일. 출력 키 = DB 컬럼 이름

    row = extract(text)                              # 제출할 때 (규칙 + LLM)
    results = search(**to_search_args(text, row))    # RAG 검색
    judge_in = to_judge_profile(row)                 # 판정 입력 (한국어 키)

- extract_quick(text) : 입력 중. 규칙만 (API 안 씀) -> 인식된 정보 / 빠진 정보
- ASK_TEXT[값] : ask_fields 값 -> 빠진 정보 문구
"""
from extract_rules import extract_rules
from extract_llm import extract as _extract_llm

ASK_TEXT = {
    "만나이": "나이 (만 나이, 예: 만 27세)",
    "거주지": "거주지 구 (서울 기준, 예: 마포구)",
    "창업예정지": "창업 예정 구 (예: 성동구)",
    "사업장소재지": "사업장 소재지 구 (예: 성동구)",
    "업력_개월": "창업 후 개월 수 (예: 창업 18개월째)",
    "업종": "업종 (예: 디저트 카페)",
    "need": "필요한 지원 (예: 자금, 교육, 공간, 홍보)",
}

PLACES = {"res": "거주지", "plan": "창업예정지", "biz": "사업장소재지"}
FIELDS = {"age": "만나이", "stage": "창업단계", "biz_months": "업력_개월", "industry_cat": "업종",
          "biz_type": "사업자_형태", "gender": "성별", "special_quals": "특수자격",
          "industry_raw": "industry", "need": "need", "ask_fields": "되묻기_유도"}


def to_row(text, p):
    """추출 결과 (한국어 키) -> DB 컬럼 이름"""
    row = {"input_text": text}
    for k, name in PLACES.items():
        x = p[name]
        row.update({f"{k}_sido": x["시도"], f"{k}_sigungu": x["시군구"], f"{k}_raw": x["원문"], f"{k}_candidates": x["후보_구"]})
    for k, name in FIELDS.items():
        row[k] = p[name]
    return row


def extract_quick(text):
    """입력 중 (규칙만)"""
    return to_row(text, extract_rules(text))


def extract(text):
    """제출할 때 (규칙 + LLM)"""
    return to_row(text, _extract_llm(text))


def to_search_args(text, row):
    """-> search() 인자 (null은 "")"""
    pre = row["stage"] != "초기창업"                  # null이면 예비로 봄
    k = "plan" if pre else "biz"
    gu = row[f"{k}_sigungu"] if row[f"{k}_sido"] == "서울특별시" and row[f"{k}_sigungu"] else ""
    return {
        "query": text,
        "user_gu": gu,
        "stage": "예비창업" if pre else "초기창업",
        "age": row["age"] if row["age"] is not None else "",
        "need": "|".join(row["need"] or []),
        "industry_cat": "|".join(row["industry_cat"] or []),
    }   # industry는 질문 문장에 있어서 안 넘김


def to_judge_profile(row):
    """-> 판정 입력 (한국어 키 10칸 + industry + need)
    industry는 업종이 기타 · 부분 제외일 때 판정이 원문 보는 용도, need는 LLM 판정이 씀"""
    def place(k):
        return {"시도": row[f"{k}_sido"], "권역": None, "시군구": row[f"{k}_sigungu"]} if row[f"{k}_sido"] else None
    return {"만나이": row["age"], "거주지": place("res"), "창업단계": row["stage"], "업력_개월": row["biz_months"],
            "창업예정지": place("plan"), "사업장소재지": place("biz"), "업종": row["industry_cat"],
            "사업자_형태": row["biz_type"], "성별": row["gender"], "특수자격": row["special_quals"],
            "industry": row["industry_raw"], "need": row["need"]}


if __name__ == "__main__":
    import json
    t = "만 28세고 망원동 살아요. 성수동에서 베이글 가게 열려고 준비 중이에요. 인테리어 자금이 필요해요."
    r = extract_quick(t)                      # API 안 씀
    print(json.dumps(r, ensure_ascii=False))
    print("빠진 정보 :", [ASK_TEXT[a] for a in r["ask_fields"] or []])
    print("검색 인자 :", to_search_args(t, r))
