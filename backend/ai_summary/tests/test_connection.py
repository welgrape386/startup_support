"""실제 연결 형식 테스트: 판정 결과(judge JSON) + 사용자 추출 결과(profile) → 3줄"""
from datetime import date

import pytest
from conftest import JUDGE

from ai_summary import make_ai_summary
from ai_summary.core.inputs import build_items, build_user_summary, to_date

TODAY = date(2026, 11, 24)
USERS = sorted({r["user_id"] for r in JUDGE})


def judge_of(uid):
    return [r for r in JUDGE if r["user_id"] == uid]


# 예은님 추출 출력 형식 그대로
PROFILE = {
    "input_text": "신사동 사는 31살이고 망원동에 카페 차리려고 해요. 인테리어 자금이 필요해요",
    "res_sido": "서울특별시", "res_sigungu": None, "res_raw": "신사동", "res_candidates": ["강남구", "관악구", "은평구"],
    "plan_sido": "서울특별시", "plan_sigungu": "마포구", "plan_raw": "망원동", "plan_candidates": None,
    "biz_sido": None, "biz_sigungu": None, "biz_raw": None, "biz_candidates": None,
    "age": 31, "stage": "예비창업", "biz_months": 0, "industry_cat": ["음식·카페"],
    "biz_type": None, "gender": None, "special_quals": None, "industry_raw": "카페 ",
    "need": ["자금"], "ask_fields": ["거주지"],
}


def test_signal_emoji_mapping():
    items = build_items(judge_of("U02"), {}, None)
    assert {i["verdict"] for i in items} == {"green", "yellow", "red", "white"}


@pytest.mark.parametrize("uid", USERS)
def test_every_user_gets_lines(uid, fake_llm):
    r = make_ai_summary(judge_of(uid), PROFILE, today=TODAY, llm=fake_llm)
    p, lines = r["payload"], r["lines"]
    n = len(judge_of(uid))
    assert p["green"] + p["yellow"] + p["red"] + p["white"] == n
    assert lines[0].startswith("지금 신청 가능")
    assert 2 <= len(lines) <= 3
    if p["green"]:
        assert lines[1].startswith("추천 공고는 '") and lines[1].endswith("지원해요.")


def test_u01_one_green(fake_llm):
    # U01: 🟢1 🟡7 🔴21 ⚪1 → green 1건이 그대로 추천됨
    r = make_ai_summary(judge_of("U01"), PROFILE, today=TODAY, llm=fake_llm)
    assert r["lines"][0] == "지금 신청 가능 1개, 조건 변경 시 가능 7개, 판단 어려운 공고 1개예요."
    assert r["lines"][1] == ("추천 공고는 '2026년 농식품 크라우드펀딩 지원사업 공고'로 "
                             "펀딩 컨설팅·수수료 최대 4백만원을 지원해요.")
    assert len(r["lines"]) == 2                                  # 마감일을 안 넘겼으니 line3 없음


def test_deadlines_make_line3(fake_llm):
    js = judge_of("U01")
    green_id = [x["pblancId"] for x in js if x["signal"] == "🟢"][0]
    r = make_ai_summary(js, PROFILE, deadlines={green_id: "2026-11-30"}, today=TODAY, llm=fake_llm)
    assert r["lines"][2].endswith("6일 후 마감되니 서둘러 확인하세요.")


def test_profile_need_null(fake_llm):
    r = make_ai_summary(judge_of("U04"), dict(PROFILE, need=None), today=TODAY, llm=fake_llm)
    assert r["lines"][1].startswith("추천 공고는")


def test_no_profile(fake_llm):
    r = make_ai_summary(judge_of("U04"), None, today=TODAY, llm=fake_llm)
    assert r["payload"]["user_summary"] == ""


def test_user_summary():
    assert build_user_summary(PROFILE) == "마포구 창업 예정, 예비창업, 31세, 음식·카페"


@pytest.mark.parametrize("v, expected", [
    ("2026-12-31", date(2026, 12, 31)), ("20261231", date(2026, 12, 31)),
    ("2026.12.31", date(2026, 12, 31)), ("2026-12-31 18:00:00", date(2026, 12, 31)),
    ("2026-11-01 ~ 2026-11-30", date(2026, 11, 30)), ("20261101 ~ 20261130", date(2026, 11, 30)),
    (None, None), ("", None), ("상시", None), ("미정", None), ("예산 소진시까지", None),
])
def test_to_date(v, expected):
    assert to_date(v) == expected


def test_no_api_key_does_not_crash(monkeypatch):
    # 키가 없어도 서비스는 멈추지 않고 원문 첫 항목으로 문장을 만든다
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import ai_summary.llm.client as c
    monkeypatch.setattr(c, "_client", None)
    monkeypatch.setattr(c, "load_dotenv", lambda *a, **k: None, raising=False)
    r = make_ai_summary(judge_of("U04"), PROFILE, today=TODAY)
    assert r["lines"][1].startswith("추천 공고는")


def test_db_title_overrides(fake_llm):
    js = [dict(r, title="[서울] DB 공고명 테스트 공고") for r in judge_of("U01")]
    r = make_ai_summary(js, PROFILE, today=TODAY, llm=fake_llm)
    assert r["lines"][1].startswith("추천 공고는 'DB 공고명 테스트 공고'로")


def test_llm_gate_render(monkeypatch):
    from ai_summary.llm.client import llm_enabled
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("ENABLE_PUBLIC_LLM", "false")
    assert llm_enabled() is False
    monkeypatch.setenv("ENABLE_PUBLIC_LLM", "true")
    assert llm_enabled() is True
    monkeypatch.setenv("AI_SUMMARY_LLM", "off")
    assert llm_enabled() is False
