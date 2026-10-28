"""LLM implementation. Requires OPENAI_API_KEY; never silently falls back to demo."""
from __future__ import annotations
from pathlib import Path
import os
from .schema import ExtractionResult
from .normalization import normalize_result

PROMPT_PATH=Path(__file__).with_name('extraction_prompt.txt')

def extract_user_info(text: str, *, user_id: str|None=None, model: str|None=None, client=None) -> dict:
    """Single-text extraction; stable JSON-compatible dict for team handoff.

    Uses a real OpenAI model unless an explicit test client is injected.
    No user text is saved locally by this function.
    """
    if not text or not text.strip(): raise ValueError('사용자 문장이 비어 있습니다.')
    if client is None:
        from openai import OpenAI
        if not os.getenv('OPENAI_API_KEY'):
            raise RuntimeError('OPENAI_API_KEY가 없습니다. README의 설정 방법을 확인하세요. 실제 LLM 결과 없이 가짜 AI 결과를 반환하지 않습니다.')
        client=OpenAI(timeout=50.0, max_retries=2)
    rsp=client.responses.parse(
        model=model or os.getenv('OPENAI_MODEL','gpt-4o-mini'),
        instructions=PROMPT_PATH.read_text(encoding='utf-8'),
        input=text,
        text_format=ExtractionResult,
        store=False,
    )
    if rsp.output_parsed is None:
        raise RuntimeError('모델에서 구조화 추출 결과를 받지 못했습니다. 응답/거절 여부를 확인하세요.')
    normalized=normalize_result(text,rsp.output_parsed,user_id=user_id)
    return normalized.model_dump(mode='json')
