"""payload → AI 요약 3줄. LLM은 case 1의 혜택 줄이기에서만 쓴다."""
from typing import Callable

from .. import config
from ..llm.benefit import shorten_benefit
from .text_utils import clean_title, eul, euro, iga


def render(p: dict, llm: Callable[[list[dict]], str]) -> list[str]:
    g, y, w = p["green"], p["yellow"], p["white"]
    line1 = config.L1.format(g=g, y=y, w=w)

    if g and p["top_green"]:                                   # case 1
        top = p["top_green"][0]
        title = clean_title(top["title"])
        benefit = shorten_benefit(top["benefit_summary"], llm)
        if benefit:
            line2 = config.L2_GREEN.format(title=title, euro=euro(title), benefit=benefit, eul=eul(benefit))
        else:                                                  # 혜택 정보가 아예 없는 공고
            line2 = f"추천 공고는 '{title}'{'이에요' if iga(title) == '이' else '예요'}."
    elif y:                                                    # case 2
        line2 = config.L2_YELLOW.format(y=y)
    elif w:                                                    # case 3
        line2 = config.L2_WHITE.format(w=w)
    else:                                                      # case 4
        line2 = config.L2_NONE

    line3 = None
    u = p.get("most_urgent")
    if u and (g or y):
        t = clean_title(u["title"])
        when = "오늘 마감이니" if u["d_day"] == 0 else f"{u['d_day']}일 후 마감되니"
        tail = "서둘러 확인하세요." if g else "참고하세요."
        line3 = config.L3.format(title=t, iga=iga(t), when=when, tail=tail)

    return [l for l in (line1, line2, line3) if l]
