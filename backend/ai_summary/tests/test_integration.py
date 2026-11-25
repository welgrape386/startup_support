"""백엔드 연결 한 줄(attach_ai_summary) 테스트: /api/support-match 응답 모양 그대로 넣어 본다"""
from conftest import ANN

from ai_summary import attach_ai_summary


def prog(short_id, apply_end=None):
    a = ANN[short_id]
    return {"id": a["id"], "title": a["title"], "applyEnd": apply_end}


def result(short_id, signal, apply_end=None):
    return {"program": prog(short_id, apply_end), "signal": signal}


# local_demo.get_match_response() 가 돌려주는 모양 (필요한 키만)
PAYLOAD = {
    "results": [result("127250", "🟢", "2026-10-28"), result("126982", "🟢", "2026-10-20"),
                result("126100", "⚪")],
    "conditional": [result("120006", "🟡")],
    "excluded": [{"programId": ANN["119802"]["id"], "title": ANN["119802"]["title"],
                  "program": prog("119802"), "result": result("119802", "🔴")}],
    "coverage": {"asOf": "2026-10-16"},
}


def test_attach_adds_lines(fake_llm):
    p = attach_ai_summary(dict(PAYLOAD), {"_row": {"need": ["자금"]}}, llm=fake_llm)
    assert p["aiSummary"]["lines"] == [
        "지금 신청 가능 2개, 조건 변경 시 가능 1개, 판단 어려운 공고 1개예요.",
        "추천 공고는 '광진구 2026년 우리동네 소상공인 경영주치의(시설개선) 참여업체 모집 공고'로 시설개선비 최대 150만원을 지원해요.",
        "'2026년 5차 라이브커머스 제작ㆍ운영 사업 참여기업 모집 공고'가 4일 후 마감되니 서둘러 확인하세요.",
    ]


def test_rules_mode_need(fake_llm):
    ext = {"검색정보": {"필요지원": ["홍보·판매"]}}
    p = attach_ai_summary(dict(PAYLOAD), ext, llm=fake_llm)
    assert "라이브커머스" in p["aiSummary"]["lines"][1]        # need=홍보·판매 → 126982가 1위


def test_broken_payload_never_raises():
    p = attach_ai_summary({"results": "이상한 값"}, None)
    assert p["aiSummary"] == {"lines": []}


def test_empty_payload():
    p = attach_ai_summary({"results": [], "conditional": [], "excluded": [], "coverage": {"asOf": "2026-10-16"}})
    assert p["aiSummary"]["lines"] == ["지금 신청 가능 0개, 조건 변경 시 가능 0개, 판단 어려운 공고 0개예요.",
                                       "추천할 만한 공고를 찾지 못했어요."]
