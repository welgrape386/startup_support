"""LLM 호출만 담당. 다른 파일은 '메시지를 주면 글자를 돌려주는 함수'로만 LLM을 안다.
모델·회사를 바꿀 때는 이 파일만 고치면 된다.

API 키는 코드에 쓰지 않는다. 프로젝트 맨 위 폴더의 .env 파일에 OPENAI_API_KEY=... 로 넣어 두면
load_dotenv()가 읽어 환경변수로 만든다. (서버에 환경변수가 이미 있으면 그 값을 그대로 쓴다)
"""
import os
import time

from .. import config

try:
    from dotenv import load_dotenv      # pip install python-dotenv
    load_dotenv()                       # 실행 위치에서 위쪽 폴더로 올라가며 .env를 찾음
except ImportError:
    pass

_client = None


def llm_enabled() -> bool:
    """백엔드 main.py와 같은 안전장치를 따른다.
    - 키가 없으면 호출 안 함
    - Render(공개 서버)에서는 ENABLE_PUBLIC_LLM=true 일 때만 호출
    - AI_SUMMARY_LLM=off 로 AI 요약 LLM만 따로 끌 수 있음
    호출 안 하면 benefit.py가 원문 첫 항목으로 문장을 만든다 (화면은 정상)
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return False
    if os.environ.get("AI_SUMMARY_LLM", "on").strip().lower() == "off":
        return False
    if os.environ.get("RENDER") and os.environ.get("ENABLE_PUBLIC_LLM", "false").lower() != "true":
        return False
    return True


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI       # 테스트할 때는 이 함수를 쓰지 않으므로 여기서 import
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY가 없습니다. .env 파일이나 서버 환경변수를 확인하세요.")
        _client = OpenAI(api_key=key)
    return _client


def openai_chat(messages: list[dict]) -> str:
    if not llm_enabled():
        raise RuntimeError("AI 요약 LLM 호출이 꺼져 있음")
    client = _get_client()
    for attempt in range(3):            # 네트워크 오류 대비 최대 3번
        try:
            r = client.chat.completions.create(
                model=config.MODEL,
                messages=messages,
                temperature=config.TEMPERATURE,
                max_tokens=config.MAX_TOKENS,
            )
            return r.choices[0].message.content or ""
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    return ""
