import pytest

from ai_summary.core.text_utils import clean_title, eul, euro, iga


@pytest.mark.parametrize("raw, expected", [
    ("[서울] 2026년 노동환경개선컨설팅 사업 대상 모집 공고", "2026년 노동환경개선컨설팅 사업 대상 모집 공고"),
    ("2026년 전시회 부스 지원 참여 소상공인 모집 공고(고카프 킨텍스 더 파이널 시즌 PART 2)",
     "2026년 전시회 부스 지원 참여 소상공인 모집 공고"),
    ("2026년 대한민국 물산업 혁신 창업대전 (Startup Water 2026) 참가자(팀) 모집 공고",
     "2026년 대한민국 물산업 혁신 창업대전 참가자 모집 공고"),
    # 연도·차수·중간 괄호는 남긴다
    ("2026년 3차 소공인 클린제조환경조성 사업 모집 공고", "2026년 3차 소공인 클린제조환경조성 사업 모집 공고"),
    ("2026년 소상공인(법인사업자) 비즈플러스카드 지원사업 시행 공고",
     "2026년 소상공인(법인사업자) 비즈플러스카드 지원사업 시행 공고"),
])
def test_clean_title(raw, expected):
    assert clean_title(raw) == expected


@pytest.mark.parametrize("word, expected", [
    ("…모집 공고", "로"),            # 받침 없음
    ("…재공고", "로"),
    ("…시행 공고(10월 추천)", "으로"),  # 괄호 무시, '천' 받침
    ("…PART 2)", "로"),              # 2 = 이
    ("…서울", "로"),                 # ㄹ받침 → 로
])
def test_euro(word, expected):
    assert euro(word) == expected


@pytest.mark.parametrize("word, expected", [
    ("최대 6백만원", "을"),
    ("투자유치", "를"),
    ("수수료 최대 15% 인하", "를"),
    ("90%", "를"),               # 퍼센트
    ("VC 1:1 밋업", "을"),
    ("멘토링 최대 3회", "를"),
    ("직접투자 최대 5억 원·PoC 자금 최대 2천만원", "을"),
])
def test_eul(word, expected):
    assert eul(word) == expected


def test_iga():
    assert iga("…모집 공고") == "가"
    assert iga("…Track2) 사업 모집 공고") == "가"
    assert iga("…지원사업") == "이"
