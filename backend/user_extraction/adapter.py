"""
나애님 user_extract.py 출력 -> local_demo.py가 쓰는 extracted 형태로 변환

나애님 출력 (DB 컬럼명 flat dict):
  age, stage, biz_months, industry_cat, biz_type, gender, special_quals,
  industry_raw, need, ask_fields,
  res_sido, res_sigungu, res_raw, res_candidates,
  plan_sido, plan_sigungu, plan_raw, plan_candidates,
  biz_sido, biz_sigungu, biz_raw, biz_candidates

local_demo.py가 기대하는 구조 (extracted['검색정보'], ['사용자프로필'], ['추가추출값']):
  검색정보.검색시도, 검색정보.검색지역, 검색정보.업종원문표현, 검색정보.필요지원,
  추가추출값.나이_언급, 추가추출값.창업단계_언급,
  사용자프로필.성별

to_search_args()가 반환하는 RAG 인자도 같이 돌려줌:
  query, user_gu, stage('예비'/'개업'/''), age, need, industry_cat
"""
from __future__ import annotations


def _stage_en(stage: str | None) -> str:
    """나애님 stage -> local_demo.py 가 쓰는 값"""
    if stage == "예비창업":
        return "예비"
    if stage == "초기창업":
        return "개업"
    return ""


def to_legacy(row: dict) -> dict:
    """
    나애님 extract/extract_quick 결과 -> local_demo.get_match_response 의 extracted 인자
    """
    stage = row.get("stage")
    pre = stage != "초기창업"          # None이면 예비로 봄

    # 사업장 지역: 예비창업이면 창업예정지(plan), 기창업이면 사업장소재지(biz)
    biz_prefix = "plan" if pre else "biz"
    biz_sido = row.get(f"{biz_prefix}_sido")
    biz_sigungu = row.get(f"{biz_prefix}_sigungu")

    # 검색에 넘길 구: 서울이고 구를 알 때만
    user_gu = biz_sigungu if biz_sido == "서울특별시" and biz_sigungu else ""

    need_list = row.get("need") or []
    industry_cat_list = row.get("industry_cat") or []

    return {
        "검색정보": {
            "검색시도": biz_sido,
            "검색지역": user_gu or biz_sigungu,
            "업종원문표현": row.get("industry_raw"),
            "필요지원": need_list,
            "필요지원키워드": need_list,
            "상황키워드": [],
        },
        "추가추출값": {
            "나이_언급": row.get("age"),
            "창업단계_언급": _stage_en(stage),
        },
        "사용자프로필": {
            "성별": row.get("gender"),
        },
        # local_demo.py의 RAG 검색 인자용 (sx dict)
        "_rag": {
            "query": row.get("input_text", ""),
            "user_gu": user_gu,
            "stage": _stage_en(stage),
            "age": str(row.get("age") or ""),
            "need": "|".join(need_list),
            "industry_cat": "|".join(industry_cat_list),
        },
    }


def to_missing(row: dict, ask_text: dict) -> list[str]:
    """
    ask_fields -> 프론트 'missing' 배열 (UI 표시용 한국어 문구)
    ask_text: user_extract.ASK_TEXT dict
    """
    return [ask_text.get(f, f) for f in (row.get("ask_fields") or [])]
