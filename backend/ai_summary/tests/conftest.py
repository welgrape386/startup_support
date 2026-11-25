"""테스트 공용 준비물. 실제 API를 부르지 않는다(비용 0원).

- ANN: data/files 의 실제 공고 62건 (loader로 읽음)
- JUDGE: 판정 파트의 judge_p1_gold_v2_detail.json (300쌍)
- FakeLLM: STAGE 3 평가 CSV에 남은 gpt-4.1-mini의 실제 응답을 그대로 돌려주는 가짜 LLM
"""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # ai_summary 폴더의 상위

from ai_summary.data.loader import load_announcements  # noqa: E402

FIX = Path(__file__).parent / "fixtures"

# 공고 정보: 공고ID 뒤 6자리로 찾기 쉽게
ANN = {pid[-6:]: dict(v, id=pid) for pid, v in load_announcements().items()}

# 판정 파트가 준 실제 판정 결과 (공고 30건 × 사용자 10명 = 300쌍)
JUDGE = json.loads((FIX / "judge_p1_gold_v2_detail.json").read_text(encoding="utf-8"))

# STAGE 3 실제 LLM 응답: {혜택 요약: [첫 응답, 재요청 응답]}
with open(FIX / "eval_stage3_v7_gpt-4.1-mini.csv", encoding="utf-8-sig") as f:
    LLM_REPLIES = {r["혜택 요약"]: r["LLM 원본응답"].split(" || ") for r in csv.DictReader(f)}


class FakeLLM:
    """benefit_summary로 v7 실제 응답을 찾아 돌려준다. 재요청이면 두 번째 응답."""

    def __init__(self, replies=None):
        self.replies = replies if replies is not None else LLM_REPLIES
        self.calls = 0

    def __call__(self, messages):
        self.calls += 1
        src = json.loads(messages[1]["content"])["benefit_summary"]
        answers = self.replies[src]
        turn = sum(m["role"] == "assistant" for m in messages)   # 0 = 첫 요청, 1 = 재요청
        return answers[min(turn, len(answers) - 1)]


@pytest.fixture
def fake_llm():
    return FakeLLM()


def item(short_id, verdict="green", apply_end=None, **override):
    """실제 공고 1건 + 판정 결과로 items 한 건을 만든다."""
    a = dict(ANN[short_id])
    a.update(verdict=verdict, apply_end=apply_end, support_amount=None)
    a.update(override)
    return a
