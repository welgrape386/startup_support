"""혜택 요약을 24자 이내로 줄인다. (평가를 통과한 v7 프롬프트 + 서버 s2)

    shorten_benefit("고용보험료 50~80% 최대 5년 환급", llm)  →  "고용보험료 50~80% 최대 5년 환급"

LLM이 실패하거나 엉뚱하게 답해도 예외를 내지 않고, 원문 첫 항목으로 대체한다.
"""
import json
import re
from pathlib import Path
from typing import Callable

from .. import config

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "benefit_v7.txt").read_text(encoding="utf-8").strip()

KEY_TERMS = ["최대", "인하", "환급", "감면", "할인", "융자", "무상", "한도", "1인당"]
UNIT_RE = re.compile(
    r"[\d,~.]+\s*(?:억\s*원|억|천만\s*원|백만\s*원|만\s*원|천\s*원|원|%p|%|회|개월|년|명|개|건|점|일)"
)


def parse_benefit(text: str) -> str:
    """LLM 응답 {"benefit": "..."} 에서 값만 꺼낸다. 못 꺼내면 ''."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return str(json.loads(m.group(0)).get("benefit", "")).strip() if m else ""
    except Exception:
        return ""


def strip_tail(b: str) -> str:
    """끝에 남은 '지원/제공/운영' 제거 → '…지원을 지원해요' 방지"""
    t = re.sub(r"\s*(지원|제공|운영)$", "", b).strip()
    return t if t else b


def keeps_key_terms(before: str, after: str) -> bool:
    """다시 줄인 결과(after)가 핵심어 개수·숫자+단위를 그대로 지켰는지"""
    for k in KEY_TERMS:
        if after.count(k) < before.count(k):
            return False
    return all(u in after for u in UNIT_RE.findall(before))


def fallback(benefit_summary: str) -> str:
    """LLM 실패 시: 원문의 첫 '·' 또는 ',' 앞부분"""
    return strip_tail(re.split(r"[·,]", benefit_summary)[0].strip())


def shorten_benefit(benefit_summary: str, llm: Callable[[list[dict]], str]) -> str:
    if not benefit_summary:
        return ""
    user = json.dumps({"benefit_summary": benefit_summary}, ensure_ascii=False)
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]
    try:
        raw = llm(msgs)
    except Exception:
        return fallback(benefit_summary)

    b = strip_tail(parse_benefit(raw))
    if not b:
        return fallback(benefit_summary)

    if len(b) > config.MAX_LEN:        # 너무 길면 1번만 다시 요청
        msgs += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content":
                f'결과 "{b}"는 {len(b)}자입니다. 같은 규칙으로 {config.MAX_LEN}자 이내가 되게 다시 줄여 주세요. '
                "금액·숫자·단위와 '최대', '인하', '환급', '융자', '한도' 같은 말은 지우지 말고, "
                '꾸미는 말이나 금액 없는 항목부터 지우세요. {"benefit": "..."}로만 답하세요.'},
        ]
        try:
            b2 = strip_tail(parse_benefit(llm(msgs)))
        except Exception:
            b2 = ""
        if b2 and keeps_key_terms(b, b2):
            b = b2                     # 핵심어를 잃었으면 첫 결과 유지
    return b
