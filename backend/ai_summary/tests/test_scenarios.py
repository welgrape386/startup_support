"""시나리오 테스트: 판정 결과(items) → 최종 3줄. 오늘 = 2026-11-24 로 고정.
"""
from datetime import date

from conftest import item

from ai_summary import summarize_items

TODAY = date(2026, 11, 24)
D = lambda m, d: date(2026, m, d)
USER = "서울 종로구, 예비창업자, 32세"


def run(items, need, fake_llm):
    return summarize_items(items, need, TODAY, USER, llm=fake_llm)


# S1. green 있음 + 관심 '자금' + 마감 임박 공고 있음
def test_s1_green_need_money(fake_llm):
    items = [
        item("127250", apply_end=D(12, 20)),          # 받는 돈 150만원, 자금
        item("126965", apply_end=D(12, 31)),          # 융자 10억원, 자금
        item("126982", apply_end=D(11, 28)),          # 받는 돈 600만원, 홍보·판매 (need 불일치)
        item("120006", verdict="yellow"),
        item("119802", verdict="red"),
        item("126100", verdict="white"),
    ]
    r = run(items, ["자금"], fake_llm)
    assert [t["title"] for t in r["payload"]["top_green"]] == [
        "광진구 2026년 우리동네 소상공인 경영주치의(시설개선) 참여업체 모집 공고",
        "2026년 중소벤처기업부 소상공인 정책자금 융자사업 5차 변경 공고",
    ]
    assert r["lines"] == [
        "지금 신청 가능 3개, 조건 변경 시 가능 1개, 판단 어려운 공고 1개예요.",
        "추천 공고는 '광진구 2026년 우리동네 소상공인 경영주치의(시설개선) 참여업체 모집 공고'로 시설개선비 최대 150만원을 지원해요.",
        "'2026년 5차 라이브커머스 제작ㆍ운영 사업 참여기업 모집 공고'가 4일 후 마감되니 서둘러 확인하세요.",
    ]


# S2. 같은 공고, need 없음 → 금액 큰 받는 돈(600만원)이 1위
def test_s2_same_items_no_need(fake_llm):
    items = [item("127250", apply_end=D(12, 20)), item("126965", apply_end=D(12, 31)),
             item("126982", apply_end=D(11, 28))]
    r = run(items, None, fake_llm)
    assert r["lines"][1] == ("추천 공고는 '2026년 5차 라이브커머스 제작ㆍ운영 사업 참여기업 모집 공고'로 "
                             "라이브커머스 제작 최대 6백만원을 지원해요.")


# S3. need가 하나도 안 겹침 → green 전체로 진행
def test_s3_need_no_match(fake_llm):
    items = [item("127250"), item("126982")]
    r = run(items, ["제도·인증"], fake_llm)
    assert "라이브커머스 제작 최대 6백만원" in r["lines"][1]


# S4. 금액 없는 green만: 판로(입점) > 컨설팅, 마감일 모두 없음 → line3 생략
def test_s4_no_amount(fake_llm):
    items = [item("120006"), item("126872")]
    r = run(items, None, fake_llm)
    assert r["lines"] == [
        "지금 신청 가능 2개, 조건 변경 시 가능 0개, 판단 어려운 공고 0개예요.",
        "추천 공고는 '2026년 2차 해외 온라인 플랫폼 입점지원 사업 참여 소상공인 모집 공고'로 해외 플랫폼 최대 2개 입점을 지원해요.",
    ]


# S5. LLM이 끝에 '지원'을 남기는 공고 (119938) → 서버가 지움
def test_s5_tail_jiwon(fake_llm):
    r = run([item("119938")], None, fake_llm)
    assert r["lines"][1] == "추천 공고는 '2026년 농식품 기술평가 지원사업 참여업체 모집 공고'로 기술평가 수수료 90%를 지원해요."


# S6. green 0, yellow 있음 + 오늘 마감인 yellow
def test_s6_yellow_today(fake_llm):
    items = [item("123842", verdict="yellow", apply_end=D(11, 24)),
             item("126320", verdict="yellow", apply_end=D(12, 5)),
             item("119802", verdict="red"), item("126100", verdict="white")]
    r = run(items, None, fake_llm)
    assert r["lines"] == [
        "지금 신청 가능 0개, 조건 변경 시 가능 2개, 판단 어려운 공고 1개예요.",
        "조건 변경 시 신청 가능한 공고가 2건이 있으니 상세 내용을 확인해보세요.",
        "'2026년 하반기 위기 소상공인 조기발굴 및 선제지원(Track2) 사업 모집 공고'가 오늘 마감이니 참고하세요.",
    ]
    assert fake_llm.calls == 0          # case 2는 LLM을 부르지 않음


# S7. green 0, yellow 있음, 마감일 없음 → line3 생략
def test_s7_yellow_no_deadline(fake_llm):
    r = run([item("123842", verdict="yellow"), item("119802", verdict="red")], None, fake_llm)
    assert r["lines"] == [
        "지금 신청 가능 0개, 조건 변경 시 가능 1개, 판단 어려운 공고 0개예요.",
        "조건 변경 시 신청 가능한 공고가 1건이 있으니 상세 내용을 확인해보세요.",
    ]


# S8. white만
def test_s8_white_only(fake_llm):
    items = [item("126100", verdict="white", apply_end=D(11, 30)), item("119802", verdict="red")]
    r = run(items, None, fake_llm)
    assert r["lines"] == [
        "지금 신청 가능 0개, 조건 변경 시 가능 0개, 판단 어려운 공고 1개예요.",
        "판단하기 어려운 공고가 1개 있어요. 조건 더 입력하면 정확도 올라가요.",
    ]
    assert r["payload"]["most_urgent"] is None


# S9. 전부 red
def test_s9_all_red(fake_llm):
    r = run([item("119802", verdict="red"), item("126965", verdict="red")], None, fake_llm)
    assert r["lines"] == [
        "지금 신청 가능 0개, 조건 변경 시 가능 0개, 판단 어려운 공고 0개예요.",
        "추천할 만한 공고를 찾지 못했어요.",
    ]


# S10. 마감 지난 green은 most_urgent 후보에서 제외
def test_s10_past_deadline_ignored(fake_llm):
    items = [item("127250", apply_end=D(11, 20)), item("126982", apply_end=D(12, 10))]
    r = run(items, None, fake_llm)
    assert r["payload"]["most_urgent"]["d_day"] == 16
    assert r["lines"][2].endswith("16일 후 마감되니 서둘러 확인하세요.")


# S11. LLM 장애 → 원문 첫 항목으로 대체, 화면은 정상
def test_s11_llm_down():
    def broken(_):
        raise ConnectionError
    r = summarize_items([item("119817")], None, TODAY, USER, llm=broken)
    assert r["lines"][1] == "추천 공고는 '2026년 광주 창업BuS 프로그램 창업기업 모집 공고'로 액셀러레이팅 최대 440만원을 지원해요."


# S12. payload 필드 이름은 기존 그대로
def test_s12_payload_fields(fake_llm):
    r = run([item("127250", apply_end=D(12, 1))], None, fake_llm)
    p = r["payload"]
    assert set(p) == {"user_summary", "green", "yellow", "red", "white", "top_green", "most_urgent"}
    assert set(p["top_green"][0]) == {"title", "support_amount", "apply_end", "d_day", "category", "benefit_summary"}
