"""AI 3줄 요약 파트. 백엔드는 make_ai_summary 하나만 부르면 된다.

    from ai_summary import make_ai_summary

    # 백엔드 연결은 integration.py 의 attach_ai_summary(payload, extracted) 한 줄로 끝난다

    lines = make_ai_summary(
        judge_results=judge_results,   # 판정 결과 리스트 (이 사용자 것만, signal 🟢🟡🔴⚪)
        profile=row,                   # user_extract.extract(text) 결과
        deadlines=deadlines,           # {"PBLN_...": "2026-12-31" 또는 None}  (없으면 line3 생략)
    )["lines"]

폴더
  core/   규칙 (입력 변환, payload, 추천 순서, 문장 조립, 조사)   ← LLM 없음
  llm/    LLM 호출과 혜택 24자 줄이기, 프롬프트
  data/   공고 데이터 CSV와 읽는 코드
  tests/  테스트 (API 호출 없음)
"""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Callable, Optional

from .core.inputs import build_items, build_user_summary, get_need
from .core.payload import build_payload
from .core.render import render
from .data.loader import load_announcements

KST = timezone(timedelta(hours=9))


@lru_cache(maxsize=1)
def _announcements() -> dict:
    """공고 CSV는 처음 한 번만 읽고 계속 재사용"""
    return load_announcements()


def summarize_items(items: list[dict], need, today: date, user_summary: str,
                    llm: Optional[Callable[[list[dict]], str]] = None) -> dict:
    """내부 형식(items)으로 바로 요약. 테스트·디버깅용."""
    if llm is None:
        from .llm.client import openai_chat
        llm = openai_chat
    payload = build_payload(items, need, today, user_summary)
    return {"payload": payload, "lines": render(payload, llm)}


def make_ai_summary(judge_results: list[dict], profile: Optional[dict] = None,
                    deadlines: Optional[dict] = None, today: Optional[date] = None,
                    llm: Optional[Callable[[list[dict]], str]] = None) -> dict:
    """판정 결과 + 사용자 추출 결과 → {"lines": [1~3줄], "payload": {...}}"""
    today = today or datetime.now(KST).date()
    items = build_items(judge_results, _announcements(), deadlines)
    return summarize_items(items, get_need(profile), today, build_user_summary(profile), llm)


from .integration import attach_ai_summary  # noqa: E402  (백엔드 연결용 한 줄 함수)

__all__ = ["make_ai_summary", "summarize_items", "attach_ai_summary"]
