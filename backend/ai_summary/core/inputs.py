"""다른 파트에서 받은 값 → AI 요약 내부 형식(items)으로 바꾼다.

  판정 결과 (judge, 나애님)      : [{"pblancId", "signal": "🟢🟡🔴⚪", ...}, ...]
  사용자 추출 결과 (extract, 예은님): {"need": [...] 또는 null, "age", "stage", "res_sigungu", ...}
  마감일 (백엔드 공고 DB)         : {"PBLN_...": announcements.apply_end (date) 또는 None(상시·rolling)}

필드 이름이 바뀌면 이 파일 위쪽의 상수만 고치면 된다.
"""
import re
from datetime import date, datetime
from typing import Optional

# ---- 판정 결과 필드 ----
JUDGE_ID = "pblancId"
JUDGE_SIGNAL = "signal"
SIGNAL_TO_VERDICT = {
    "🟢": "green", "🟡": "yellow", "🔴": "red", "⚪": "white",
    # 혹시 글자로 올 때 대비
    "green": "green", "yellow": "yellow", "red": "red", "white": "white",
}

# ---- 사용자 추출 필드 ----
PROFILE_NEED = "need"


def to_date(v):
    """마감일 값 → date 또는 None(상시)

    '2026-12-31' / '20261231' / '2026.12.31' / date / datetime 모두 처리.
    '2026-11-01 ~ 2026-11-30' 처럼 접수 기간이 통째로 오면 마지막 날짜(마감일)를 쓴다.
    """
    if v in (None, "", "상시"):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    found = re.findall(r"(\d{4})[-./]?(\d{1,2})[-./]?(\d{1,2})", str(v))
    for y, m, d in reversed(found):               # 뒤에 있는 날짜(마감일)부터
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            continue
    return None          # 알 수 없는 형식이면 마감일 없음으로 처리 (line3 생략)


def build_items(judge_results: list[dict], ann: dict, deadlines: Optional[dict] = None) -> list[dict]:
    """판정 결과 1건 = items 1건. 공고 정보(ann)와 마감일(deadlines)을 붙인다."""
    deadlines = deadlines or {}
    items = []
    for r in judge_results:
        pid = r[JUDGE_ID]
        verdict = SIGNAL_TO_VERDICT.get(str(r.get(JUDGE_SIGNAL, "")).strip())
        if verdict is None:
            continue                              # 신호등 값이 없거나 모르는 값이면 건너뜀
        a = ann.get(pid, {})
        items.append({
            "id": pid,
            "verdict": verdict,
            "title": r.get("title") or a.get("title") or pid,    # 백엔드가 DB 공고명을 넘기면 그걸 우선
            "apply_end": to_date(deadlines.get(pid)),
            "support_amount": None,
            "benefit_summary": a.get("benefit_summary", ""),
            "category": a.get("category", []),
            "amt_grant": a.get("amt_grant"),
            "amt_loan_invest": a.get("amt_loan_invest"),
            "amt_rnd": a.get("amt_rnd"),
            "support_types": a.get("support_types", []),
        })
    return items


def get_need(profile: Optional[dict]):
    return (profile or {}).get(PROFILE_NEED)       # None 이면 ① 필터 건너뜀


def build_user_summary(profile: Optional[dict]) -> str:
    """payload.user_summary (문장에는 안 쓰고 로그용). 예: '마포구 창업 예정, 예비창업, 31세, 음식·카페'"""
    p = profile or {}
    parts = []
    if p.get("stage") == "초기창업" and p.get("biz_sigungu"):
        parts.append(f"{p['biz_sigungu']} 사업장")
    elif p.get("plan_sigungu"):
        parts.append(f"{p['plan_sigungu']} 창업 예정")
    elif p.get("res_sigungu"):
        parts.append(f"{p['res_sigungu']} 거주")
    if p.get("stage"):
        parts.append(p["stage"])
    if p.get("age") is not None:
        parts.append(f"{p['age']}세")
    if p.get("industry_cat"):
        parts.append("/".join(p["industry_cat"]))
    return ", ".join(parts)
