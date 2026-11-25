from conftest import FakeLLM

from ai_summary.llm.benefit import keeps_key_terms, shorten_benefit, strip_tail


# ---------- 서버 규칙 ----------
def test_strip_tail():
    assert strip_tail("기술평가 수수료 90% 지원") == "기술평가 수수료 90%"
    assert strip_tail("공유오피스 공간 제공") == "공유오피스 공간"
    assert strip_tail("지원") == "지원"                         # 다 지워지면 그대로
    assert strip_tail("변호사 선임") == "변호사 선임"


def test_keeps_key_terms():
    # '원' 단위가 빠짐 (127098) → 거부
    assert not keeps_key_terms("직접투자 최대 5억 원·PoC 자금 최대 2천만원", "직접투자 최대 5억·PoC 자금 최대 2천만원")
    # '최대' 2개 → 1개 (127234) → 거부
    assert not keeps_key_terms("시상금 최대 1천만원·사업화지원금 최대 3천만원", "시상금 최대 1천만원·사업화지원금 3천만원")
    # '인하'가 빠짐 (121480 v6) → 거부
    assert not keeps_key_terms("홈쇼핑 방송 2회·수수료 최대 15% 인하", "홈쇼핑 방송 2회·수수료 최대 15%")
    # 꾸밈말만 빠짐 → 허용
    assert keeps_key_terms("소상공인 정책자금 융자 최대 10억원·금리우대", "정책자금 융자 최대 10억원·금리우대")


# ---------- 실제 v7 응답으로 ----------
def test_short_enough_one_call(fake_llm):
    assert shorten_benefit("고용보험료 50~80% 최대 5년 환급", fake_llm) == "고용보험료 50~80% 최대 5년 환급"
    assert fake_llm.calls == 1


def test_tail_jiwon_removed(fake_llm):        # 119938: LLM이 '지원'을 남김 → 서버가 지움
    assert shorten_benefit("기술평가 수수료 90% 지원", fake_llm) == "기술평가 수수료 90%"


def test_retry_rejected_keeps_first():        # 재요청 결과가 '원'을 잃으면 첫 결과
    llm = FakeLLM({"X": ['{"benefit": "직접투자 최대 5억 원·PoC 자금 최대 2천만원"}',
                         '{"benefit": "직접투자 최대 5억·PoC 자금 최대 2천만원"}']})
    assert shorten_benefit("X", llm) == "직접투자 최대 5억 원·PoC 자금 최대 2천만원"
    assert llm.calls == 2


def test_retry_accepted():
    llm = FakeLLM({"X": ['{"benefit": "소상공인 정책자금 융자 최대 10억원·금리우대"}',
                         '{"benefit": "정책자금 융자 최대 10억원·금리우대"}']})
    assert shorten_benefit("X", llm) == "정책자금 융자 최대 10억원·금리우대"


# ---------- LLM이 망가져도 서비스는 계속 ----------
def test_fallback_bad_json():
    llm = FakeLLM({"창업교육 최대 300만원·판로개척 프로그램": ["죄송합니다"]})
    assert shorten_benefit("창업교육 최대 300만원·판로개척 프로그램", llm) == "창업교육 최대 300만원"


def test_fallback_exception():
    def broken(_):
        raise TimeoutError
    assert shorten_benefit("컨설팅 바우처·투자유치 지원", broken) == "컨설팅 바우처"


def test_empty_input(fake_llm):
    assert shorten_benefit("", fake_llm) == ""
    assert fake_llm.calls == 0
