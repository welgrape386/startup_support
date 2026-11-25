"""판정 결과(items) → payload 만들기. payload 필드 이름은 기존 그대로다.

items 한 건 (판정 엔진이 백엔드에 넘겨주는 값):
{
  "id": "PBLN_000000000119817",
  "title": "2026년 광주 창업BuS 프로그램 창업기업 모집 공고",   # 원문 공고명
  "verdict": "green" | "yellow" | "red" | "white",
  "apply_end": date | None,                                   # None = 상시
  "support_amount": "최대 440만원",
  "category": ["자금", "교육·컨설팅"],
  "benefit_summary": "액셀러레이팅 최대 440만원, 투자 유치 프로그램",
  # ↓ 추천 순서에만 쓰고 payload에는 넣지 않음
  "amt_grant": 440,        # 최대지원금_받는돈(만원), 없으면 None
  "amt_loan_invest": None, # 최대지원금_융자·투자(만원)
  "amt_rnd": None,         # 최대지원금_R&D(만원)
  "support_types": ["보조금·사업화자금", "투자·IR"],
}
"""
import re
from datetime import date

from .. import config
from .ranking import rank_green


def _d_day(apply_end, today: date):
    return (apply_end - today).days if apply_end else None


def _strip_region(t: str) -> str:
    return re.sub(r"^\[서울\]\s*", "", t)


def build_payload(items: list[dict], need, today: date, user_summary: str) -> dict:
    p = {"user_summary": user_summary}
    for k in ("green", "yellow", "red", "white"):
        p[k] = sum(i["verdict"] == k for i in items)

    greens = [dict(i, d_day=_d_day(i["apply_end"], today)) for i in items if i["verdict"] == "green"]
    p["top_green"] = [{
        "title": _strip_region(a["title"]),
        "support_amount": a.get("support_amount"),
        "apply_end": a["apply_end"].isoformat() if a["apply_end"] else None,
        "d_day": a["d_day"],
        "category": a.get("category", []),
        "benefit_summary": a.get("benefit_summary", ""),
    } for a in rank_green(greens, need)[:config.TOP_N]]

    color = "green" if p["green"] else "yellow" if p["yellow"] else None
    cands = [i for i in items if color and i["verdict"] == color
             and i["apply_end"] and _d_day(i["apply_end"], today) >= 0]
    u = min(cands, key=lambda i: (i["apply_end"], i["id"]), default=None)
    p["most_urgent"] = {
        "title": _strip_region(u["title"]),
        "apply_end": u["apply_end"].isoformat(),
        "d_day": _d_day(u["apply_end"], today),
    } if u else None
    return p
