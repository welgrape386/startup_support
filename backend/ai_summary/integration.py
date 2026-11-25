"""백엔드 연결용. /api/support-match 응답(payload)만 보고 AI 3줄 요약을 붙인다.

백엔드(main.py)에서 할 일은 이것뿐:

    payload = get_match_response(request, session, extracted=extracted)
    attach_ai_summary(payload, extracted)        # ← 이 한 줄 추가
    return payload

- 판정 신호등: payload["results"] / ["conditional"] / ["excluded"][i]["result"] 의 "signal"
- 공고 ID·공고명·마감일: 각 결과의 program["id"], ["title"], ["applyEnd"]
- 기준일: payload["coverage"]["asOf"] (= local_demo.JUDGE_AS_OF, 카드 D-day와 같은 기준)
- need: extracted["_row"]["need"] (llm 모드) 또는 extracted["검색정보"]["필요지원"] (rules 모드)

어떤 오류가 나도 예외를 밖으로 던지지 않는다. 실패하면 aiSummary.lines = [] (프론트는 요약 상자만 숨김).
"""
import logging
from typing import Optional

from . import make_ai_summary
from .core.inputs import to_date

log = logging.getLogger(__name__)


def _shown_results(payload: dict) -> list[dict]:
    """화면에 나간 판정 결과 전체: 🟢⚪(results) + 🟡(conditional) + 🔴(excluded)"""
    rows = list(payload.get("results") or []) + list(payload.get("conditional") or [])
    for e in payload.get("excluded") or []:
        r = e.get("result")
        if r is None:      # result가 없으면 최소 정보로 🔴 처리
            r = {"signal": "🔴", "program": e.get("program") or {"id": e.get("programId"), "title": e.get("title")}}
        rows.append(r)
    return rows


def _profile(extracted: Optional[dict]) -> Optional[dict]:
    if not extracted:
        return None
    row = extracted.get("_row")
    if row is not None:
        return row
    needs = [x for x in (extracted.get("검색정보") or {}).get("필요지원", []) if x != "미지정"]
    return {"need": needs or None}


def ai_summary_lines(payload: dict, extracted: Optional[dict] = None, llm=None) -> list[str]:
    try:
        judge_results, deadlines = [], {}
        for r in _shown_results(payload):
            p = r.get("program") or {}
            pid = p.get("id")
            if not pid:
                continue
            judge_results.append({"pblancId": pid, "signal": r.get("signal"), "title": p.get("title")})
            deadlines[pid] = p.get("applyEnd")            # 'YYYY-MM-DD' 또는 None(상시)
        today = to_date((payload.get("coverage") or {}).get("asOf"))
        return make_ai_summary(judge_results, profile=_profile(extracted),
                               deadlines=deadlines, today=today, llm=llm)["lines"]
    except Exception as e:  # noqa: BLE001
        log.warning("AI 요약 실패, 요약 없이 계속: %s", e)
        return []


def attach_ai_summary(payload: dict, extracted: Optional[dict] = None, llm=None) -> dict:
    """payload에 aiSummary를 넣고 그대로 돌려준다. (llm은 테스트용, 보통 비워 둠)"""
    payload["aiSummary"] = {"lines": ai_summary_lines(payload, extracted, llm)}
    return payload
