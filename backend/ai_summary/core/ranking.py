"""green 공고의 추천 순서 (규칙만, LLM 없음)

① 관심 카테고리(need)와 하나라도 겹치는 공고만 남김
   need가 없거나(None/[]/"미지정") 겹치는 공고가 없으면 green 전체
② 금액 있는 공고:  받는 돈 큰 순 → 융자·카드·투자 큰 순 → R&D 큰 순
③ 금액 없는 공고:  컨설팅·상담·교육·법률이 '아닌' 유형이 있는 공고 → 그 외(컨설팅류만)
④ 동점이면 마감 여유(d_day ≥ 7 → 상시 → d_day < 7) → 공고ID 순
"""
from .. import config


def _norm(s: str) -> str:
    """'교육 · 컨설팅'과 '교육·컨설팅'을 같게 보려고 공백 제거"""
    return s.replace(" ", "")


def filter_by_need(greens: list[dict], need) -> list[dict]:
    if isinstance(need, str):
        need = [need]
    wanted = {_norm(n) for n in (need or []) if n and n != "미지정"}
    if not wanted:
        return greens
    hit = [a for a in greens if wanted & {_norm(c) for c in a.get("category", [])}]
    return hit or greens


def _amount_group(a: dict) -> tuple[int, float]:
    if a.get("amt_grant"):
        return 0, a["amt_grant"]
    if a.get("amt_loan_invest"):
        return 1, a["amt_loan_invest"]
    if a.get("amt_rnd"):
        return 2, a["amt_rnd"]
    if set(a.get("support_types", [])) - config.CONSULT_TYPES:
        return 3, 0
    return 4, 0


def _deadline_group(d_day) -> int:
    if d_day is None:
        return 1          # 상시
    return 0 if d_day >= 7 else 2


def sort_key(a: dict):
    group, amt = _amount_group(a)
    return (group, -amt, _deadline_group(a.get("d_day")), a["id"])


def rank_green(greens: list[dict], need) -> list[dict]:
    return sorted(filter_by_need(greens, need), key=sort_key)
