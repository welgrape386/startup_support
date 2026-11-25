"""추천 순서 ①~④ (실제 공고 데이터 사용)

공고 금액 참고 (만원)
  받는 돈  : 127031 1,050 / 126982 600 / 119817 440 / 127250 150
  융자·투자: 126965 100,000 / 119802 1,000
  R&D      : 124232 600,000
  금액 없음: 126872 해외 입점(판로)  / 120006 노동환경 컨설팅(컨설팅만)
"""
from conftest import item

from ai_summary.core.ranking import filter_by_need, rank_green


def ids(rows):
    return [r["id"][-6:] for r in rows]


def test_amount_groups_order():
    # 받는 돈 → 융자·투자 → R&D → 금액 없는 비컨설팅 → 컨설팅만
    rows = [item(x) for x in ["120006", "124232", "126872", "126965", "127250"]]
    assert ids(rank_green(rows, None)) == ["127250", "126965", "124232", "126872", "120006"]


def test_rnd_after_small_grant():
    # R&D 60억원이어도 받는 돈 150만원보다 뒤, 그러나 금액 없는 공고보다는 앞 (금액 있는 공고 중 맨 뒤)
    rows = [item("124232"), item("127250"), item("126872")]
    assert ids(rank_green(rows, None)) == ["127250", "124232", "126872"]


def test_bigger_amount_first():
    rows = [item(x) for x in ["119817", "127031", "126982"]]
    assert ids(rank_green(rows, None)) == ["127031", "126982", "119817"]


def test_deadline_tiebreak():
    # 둘 다 금액 없는 비컨설팅 → d_day≥7 > 상시 > d_day<7
    soon, none, far = item("126872", d_day=3), item("126100", d_day=None), item("126875", d_day=20)
    assert ids(rank_green([soon, none, far], None)) == ["126875", "126100", "126872"]


def test_id_tiebreak():
    a, b = item("126872", d_day=10), item("126100", d_day=10)
    assert ids(rank_green([a, b], None)) == ["126100", "126872"]


# ---------- ① need 필터 ----------
def test_need_filter_hits():
    rows = [item("127031"), item("126872")]            # 127031 = 공간·시설·인력 / 126872 = 홍보·판매·해외진출 등
    assert ids(rank_green(rows, ["해외진출"])) == ["126872"]


def test_need_two_values_any_match():
    # 127031 = 공간·시설·인력 / 126872 = 해외진출 포함 / 120006 = 교육·컨설팅만
    rows = [item("127031"), item("126872"), item("120006")]
    assert set(ids(filter_by_need(rows, ["해외진출", "인력"]))) == {"126872", "127031"}


def test_need_no_match_falls_back_to_all():
    rows = [item("127031"), item("126872")]
    assert len(filter_by_need(rows, ["제도·인증"])) == 2


def test_need_empty_values():
    rows = [item("127031"), item("126872")]
    for need in (None, [], "미지정", ["미지정"]):
        assert len(filter_by_need(rows, need)) == 2


def test_need_spacing_ignored():
    # 사용자 추출 값은 '교육 · 컨설팅', 공고 카테고리는 '교육·컨설팅'
    rows = [item("120006"), item("127031")]
    assert ids(filter_by_need(rows, ["교육 · 컨설팅"])) == ["120006"]
