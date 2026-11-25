from ai_summary.data.loader import load_announcements


def test_load_real_files():
    ann = load_announcements()
    assert len(ann) == 62
    a = ann["PBLN_000000000127250"]
    assert a["benefit_summary"] == "시설개선비 최대 150만원"
    assert a["amt_grant"] == 150 and a["amt_loan_invest"] is None
    assert a["category"] == ["자금", "공간·시설"]
    assert a["support_types"] == ["보조금·사업화자금", "장비·시설(현물·이용)"]
    assert all(v["category"] and v["support_types"] for v in ann.values())   # 빈 칸 없음
