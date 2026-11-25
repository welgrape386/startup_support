"""
규칙 + LLM (gpt-4.1-mini 1번)
- 업종 · industry · need -> LLM
- 창업단계 -> 규칙이 못 정하면 LLM
- 지역 -> 2곳 이상이거나 예전 얘기 있을 때만 LLM이 고른 원문으로
- 나이 · 업력 · 성별 · 사업자 형태 · 특수자격 -> 규칙만
.env에 OPENAI_API_KEY 없으면 규칙만 돌림
"""
import json, os, re, time
from pathlib import Path
from extract_rules import extract_rules, ask_fields, get_months, _mentions, _place, NEED_SURE, NEED_SOFT, WANT, SELL

CATS = ["음식·카페", "식품 제조·농식품", "도소매·판매", "생활 서비스", "공방·제조", "IT·소프트웨어", "디자인·콘텐츠", "첨단기술", "기타"]
NEEDS = ["자금", "교육·컨설팅", "공간·시설", "홍보·판매", "인력", "기술개발", "해외진출", "제도·인증", "기타"]
# 예전 얘기 있으면 지역을 LLM이 다시 봄 (경력 끊겼다가 같은 건 빼고)
PAST = r"(하|살|운영하|짓|일하|장사하)다가|하던|했던|정리했|접고|접었|이사|예전|작년에"
# 지원 단어. 하나도 없으면 넓은 질문이라 need null
# 임대만 있으면 업종일 수 있어서 임대료 · 매장 임대 · 임차만, 직원도 뽑다 · 구하다랑 같이 있을 때만
NEED_WORDS = "|".join([p for _, p in NEED_SURE + NEED_SOFT] +
                      [r"비용|보증금|지원금|장비|임대료|매장 임대|임차|매장|확장|이전|주문|멘토|직원.{0,10}(뽑|구하|채용|늘리)|뭐부터|어떻게 시작|시작할지|막막"])

# 프롬프트 출처
# - 업종 표 : 판정규칙 업종 카테고리 매핑 표 (KSIC 안 씀), 2개 기준도 판정규칙
# - need 표 : RAG make_category.py KEYWORDS
# - 예시는 일반 업종 · 말투로만 (정답셋 · 검증셋 문장 X)
# - 숙박은 기타 -> 숙박 제외 공고는 판정이 industry 원문으로 확인
PROMPT = """너는 창업 지원사업 추천 서비스에서 사용자가 쓴 문장 하나를 읽고 값 6개를 뽑는 역할이야.
나이 · 업력 · 성별 같은 다른 값은 코드가 뽑으니까 아래 6개만 봐.

# 공통 규칙
- 문장에 근거가 있는 것만 뽑고, 근거가 없으면 null. 추측해서 채우지 않음
- 카테고리 값은 아래 목록의 글자 그대로만 씀 (가운뎃점 · 띄어쓰기 포함)
- 사용자의 "지금 하는 사업" 또는 "앞으로 할 사업"만 봄. 예전에 했다가 그만둔 사업 · 예전에 있던 곳은 빼기

# 1. 업종 : 카테고리 1~2개 list, 첫 번째가 주 업종
아래 표로 고름. 사용자 예시 · 공고 업종명 예시에 없으면 기준 칸을 보고 가장 가까운 카테고리로

| 카테고리 | 기준 | 사용자 예시 | 공고 업종명 예시 |
| 음식·카페 | 매장에서 음식 · 음료를 만들어 바로 파는 곳 | 카페, 분식집, 치킨집, 한식당, 일식집, 주점, 제과점, 샐러드 전문점 | 음식업, 외식 |
| 식품 제조·농식품 | 식품을 만들어 파는 브랜드 · 제조, 농업 | 수제 잼, 수제 소스, 디저트 브랜드, 전통주 제조, 즙 · 청 가공, 밀키트 제조, 농산물 재배 | 식품 관련 기업, 농식품, 농업 |
| 도소매·판매 | 직접 만들지 않은 물건을 파는 곳, 온라인 판매 포함 | 꽃집, 서점, 반찬가게, 편의점, 온라인 쇼핑몰, 안경점, 생활용품점, 식자재 유통 | 소매업, 도소매, 유통 |
| 생활 서비스 | 사람 · 물건을 돌보는 서비스 | 미용실, 네일숍, 반려동물 미용, 한복 대여, 수선, 코인세탁, 열쇠 · 수리점, 청소 대행, 펫호텔 | 서비스업 |
| 공방·제조 | 식품이 아닌 물건을 만드는 곳 | 가죽 공방, 핸드메이드 소품, 인쇄소, 금속 공예, 유리 공예, 의류 봉제, 가방 제작 | 소공인, 제조업, 가죽 · 패션 제조 |
| IT·소프트웨어 | 소프트웨어를 만드는 사업 (온라인으로 일하는 것만으로는 아님) | 앱, AI 서비스, 앱 · 웹 개발, 게임 개발, 데이터 분석 서비스, 업무용 소프트웨어 | SW, 핀테크, 블록체인, 위치정보, ICT |
| 디자인·콘텐츠 | 디자인 · 콘텐츠를 만드는 사업 | 디자인 스튜디오, 브랜드 디자인, 영상 제작, 일러스트, 출판사, 사진 · 영상 촬영 스튜디오 | 디자인, 콘텐츠 |
| 첨단기술 | 연구 · 기술이 중심인 사업 | 의료기기 개발, 2차전지 소재 | 딥테크, 바이오, 반도체, 모빌리티, 에너지 · 기후, 물산업 |
| 기타 | 위 8개 어디에도 안 맞을 때만 | 원룸 임대, 숙박업, 교육 서비스, 운수 · 물류 | 부동산업 |

- 근거 없이 카테고리를 늘리지 않음 (맞지 않는 카테고리가 붙으면 받을 수 있는 지원을 놓칠 수 있음)
- 매장에서 만들어 바로 팔면 음식·카페, 브랜드로 만들어 포장 · 유통하면 식품 제조·농식품
- 9개 중 딱 맞는 칸이 없으면 가까운 칸으로 억지로 넣지 말고 기타 (숙박 · 교육 · 운수 · 부동산처럼)
- 사진 · 영상을 찍어서 만드는 사업은 디자인·콘텐츠
- 2개는 두 경우만 : 직접 만들어서 판매도 하는 경우 (예: 수제 액세서리 온라인 판매 -> 공방·제조 + 도소매·판매),
  서로 다른 두 사업을 같이 한다고 말한 경우. 두 번째에 기타는 넣지 않음
- 앞으로 이렇게 팔아보고 싶다는 계획은 업종이 아니라 need. 무슨 사업인지 말 안 했으면 null
- 무슨 사업인지 말했으면 null로 두지 않음 (9개 중 맞는 칸, 없으면 기타)

# 2. industry : 업종을 문장에 쓴 말 그대로 짧게
- 무슨 사업인지 가리키는 말만 짧게 (예: "가죽 공방", "제과점"). 조사 · 꾸밈말 · 지역, 사람 · 신분을 가리키는 말은 빼기. 없으면 null

# 3. need : 받고 싶은 지원 1~2개 list
아래 표로 고름. 사용자가 바라는 지원이 어느 지원 종류에 해당하는지 보고 같은 칸으로

| 지원 종류 | 해당하는 말 (지원사업 공고에서 쓰는 말) | 사용자 말투 예시 |
| 자금 | 융자, 대출, 보증, 정책자금, 지원금, 사업화 자금, 크라우드펀딩, 바우처, 수수료 지원, 보험료, 보조금, 이자 지원, 비용 지원, 투자, 인센티브 | 초기 비용이 모자라요 |
| 교육·컨설팅 | 교육, 컨설팅, 멘토링, 상담, 코칭, 아카데미, 진단, 클리닉, 자문, 액셀러레이팅 | 운영 노하우를 배우고 싶어요 |
| 공간·시설 | 공간, 입주, 시설, 장비, 공유주방, 점포, 매장, 인테리어, 리모델링, 간판, 공장, 작업장, 스튜디오, 임차 | 작업할 장소가 없어요 |
| 홍보·판매 | 판로, 홍보, 마케팅, 판매, 라이브커머스, 홈쇼핑, 입점, 전시회, 박람회, 쇼핑몰, 상세페이지, 기획전, 팝업, 배달, 온라인 플랫폼 | 판매처를 늘리고 싶어요 |
| 인력 | 채용, 인건비, 고용 지원, 일자리, 인턴 | 일할 사람을 구하고 싶어요 |
| 기술개발 | R&D, 기술개발, 시제품, 특허, 지식재산, 상표, 기술평가, 기술이전, 실증 | 제품을 새로 개발하고 싶어요 |
| 해외진출 | 해외, 수출, 글로벌 | 외국에도 팔아보고 싶어요 |
| 제도·인증 | 인증, 확인서, 포상, 표창 | 인증을 받고 싶어요 |
| 기타 | 지원을 바라는데 위 8개에 안 맞을 때만 | |

- 돈을 바라면 무엇에 쓸 돈이든 자금 (예: 리모델링 비용 -> 자금). 단, 기술 개발 · 시제품에 쓸 돈이면 기술개발도 같이
- 지원을 바라는 말 (필요해요 · 받고 싶어요 · 있을까요 등)이나 어려움을 털어놓는 말 (고민이에요 · 모르겠어요 · 막막해요 등)이 있을 때만 뽑음
- 사업 설명은 need 아님. 무슨 지원인지도, 무슨 어려움인지도 말하지 않은 넓은 질문 (지원 받을 수 있나요?)만 null.
  어려움을 말했으면 아래 줄대로 지원 종류로 바꿔서 뽑음
- 창업을 어떻게 시작할지 자체를 몰라 막막한 경우만 교육·컨설팅. 장사하면서 생긴 문제는 그 문제 종류대로 (손님 · 매출 -> 홍보·판매, 돈 -> 자금, 사람 -> 인력)
- 무엇을 배우고 싶다는 요청은 주제와 상관없이 교육·컨설팅 하나. 요청이 2개면 말한 순서대로

# 4. 창업단계 : "예비창업" / "초기창업" / null
- 예비창업 : 아직 사업을 시작 안 함 (준비 중 · 계획 · 하려고 · 사업자등록 전). 폐업하고 다시 시작하려는 경우도 예비창업
- 초기창업 : 지금 사업을 하고 있음 (운영 중 · 연 지 N년 · 하고 있어요 · 현재형으로 "○○ 하는데", "○○ 해요")
- 회사를 그만둔 건 폐업 아님. 단서가 없으면 null

# 5. 거주지_원문 : 사용자가 지금 사는 곳을 문장에 쓴 그대로 (예전에 살던 곳은 빼기)
- "살아요 · 사는 · 거주" 같은 말이 붙은 곳, 자취하는 곳 · 이사 온 곳도 사는 곳. 사업장을 거주지로 짐작하지 않음. 없으면 null

# 6. 사업장_원문 : 지금 사업장이나 앞으로 창업할 곳을 문장에 쓴 그대로
- 예전에 하던 곳 · 예전에 있던 곳은 빼기. 없으면 null

# 예시
문장 : 작년까지 마포구에서 하던 치킨집을 접고, 지금은 성동구에서 수제 소스 브랜드를 준비 중이에요.
답 : {"업종": ["식품 제조·농식품"], "industry": "수제 소스 브랜드", "need": null, "창업단계": "예비창업", "거주지_원문": null, "사업장_원문": "성동구"}

문장 : 은평구 살고 연신내에서 3년째 네일숍 하고 있어요. 손님이 줄어서 홍보랑 직원 인건비 지원이 필요해요.
답 : {"업종": ["생활 서비스"], "industry": "네일숍", "need": ["홍보·판매", "인력"], "창업단계": "초기창업", "거주지_원문": "은평구", "사업장_원문": "연신내"}

문장 : 직접 만든 가죽 지갑을 온라인으로 팔고 있어요.
답 : {"업종": ["공방·제조", "도소매·판매"], "industry": "가죽 지갑", "need": null, "창업단계": "초기창업", "거주지_원문": null, "사업장_원문": null}"""


def _list_or_null(enum):
    return {"anyOf": [{"type": "array", "items": {"type": "string", "enum": enum}}, {"type": "null"}]}


def _str_or_null(enum=None):
    s = {"type": "string", "enum": enum} if enum else {"type": "string"}
    return {"anyOf": [s, {"type": "null"}]}


# 답 모양 강제 (없는 카테고리 안 나오게)
SCHEMA = {"name": "user_extract", "strict": True, "schema": {
    "type": "object", "additionalProperties": False,
    "required": ["업종", "industry", "need", "창업단계", "거주지_원문", "사업장_원문"],
    "properties": {"업종": _list_or_null(CATS), "industry": _str_or_null(), "need": _list_or_null(NEEDS),
                   "창업단계": _str_or_null(["예비창업", "초기창업"]),
                   "거주지_원문": _str_or_null(), "사업장_원문": _str_or_null()}}}


def _client():
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")
    except ImportError:
        pass
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY 없음 -> 규칙만 돌림 (.env 확인)")
        return False
    from openai import OpenAI
    return OpenAI()


_CLIENT = None
MODEL = None                         # None이면 .env의 OPENAI_MODEL
STATS = {"호출": 0, "실패": 0, "초": 0.0, "입력토큰": 0, "출력토큰": 0}   # 비용 계산용


def set_model(name):
    """모델 정하고 통계 0으로"""
    global MODEL
    MODEL = name
    for k in STATS:
        STATS[k] = 0


def ask_llm(text):
    """LLM 답 dict. 키 없거나 실패하면 None"""
    global _CLIENT
    if _CLIENT is None:              # 처음 한 번만 (키 없으면 False)
        _CLIENT = _client()
    if not _CLIENT:
        return None
    t0 = time.time()
    try:
        r = _CLIENT.chat.completions.create(
            model=MODEL or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), temperature=0,
            response_format={"type": "json_schema", "json_schema": SCHEMA},
            messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": "문장 : " + text}])
        STATS["호출"] += 1
        STATS["초"] += time.time() - t0
        STATS["입력토큰"] += r.usage.prompt_tokens
        STATS["출력토큰"] += r.usage.completion_tokens
        return json.loads(r.choices[0].message.content)
    except Exception as e:                      # 실패해도 규칙 결과는 나가게
        STATS["실패"] += 1
        print("LLM 실패 -> 규칙만:", type(e).__name__, str(e)[:120])
        return None


def _pick(raw, text):
    """LLM이 고른 지역 원문 -> place"""
    if not raw or raw not in text:
        return None
    m = _mentions(raw)
    return m[0][2] if m else None


def _sure_needs(text):
    """바라는 말 있는 문장 안의 SURE need 단어만"""
    hits = []
    pos = 0
    for sent in re.split(r"(?<=[.?!])\s*", text):
        if re.search(WANT, sent):
            for need, pat in NEED_SURE:
                m = re.search(pat, sent)
                if m:
                    hits.append((pos + m.start(), need))
        pos += len(sent) + 1
    return list(dict.fromkeys(n for _, n in sorted(hits)))[:2]


def merge(text, p, llm):
    """규칙 결과 p에 LLM 답을 합침"""
    if not llm:
        return p
    cats = [c for c in (llm.get("업종") or []) if c in CATS][:2]
    if len(cats) == 1 and cats[0] in ("공방·제조", "식품 제조·농식품") and re.search(SELL, text):
        cats.append("도소매·판매")                # 만들어서 파는데 LLM이 빠뜨린 경우
    needs = [n for n in (llm.get("need") or []) if n in NEEDS][:2]
    if needs and not re.search(NEED_WORDS, text):   # 넓은 질문이면 LLM need 버림
        needs = []
    if not needs:                                   # LLM이 놓친 확실한 단어 (대출 · 라이브커머스 등)
        needs = _sure_needs(text)
    p["업종"] = cats or None                  # LLM null도 그대로 씀
    p["industry"] = llm.get("industry") or None
    p["need"] = needs or None
    if p["창업단계"] is None and llm.get("창업단계") in ("예비창업", "초기창업"):
        p["창업단계"] = llm["창업단계"]
    if len(_mentions(text)) >= 2 or re.search(PAST, text):    # 지역 헷갈릴 때만
        res, biz = _pick(llm.get("거주지_원문"), text), _pick(llm.get("사업장_원문"), text)
        p["거주지"] = res or _place()      # 서울 밖 거주도 받음
        p["창업예정지"], p["사업장소재지"] = _place(), _place()
        if biz:
            p["사업장소재지" if p["창업단계"] == "초기창업" else "창업예정지"] = biz
    # 단계에 맞춰 다시 정리
    if p["창업단계"] == "초기창업":
        if p["업력_개월"] is None:                 # LLM이 초기창업으로 정한 경우
            p["업력_개월"] = get_months(text)
        if p["창업예정지"]["시도"] and not p["사업장소재지"]["시도"]:
            p["사업장소재지"], p["창업예정지"] = p["창업예정지"], _place()
    else:
        if p["사업장소재지"]["시도"] and not p["창업예정지"]["시도"]:
            p["창업예정지"], p["사업장소재지"] = p["사업장소재지"], _place()
        if p["창업단계"] == "예비창업":
            p["업력_개월"] = 0
    p["되묻기_유도"] = ask_fields(p)
    return p


def extract(text):
    """규칙 + LLM (키 없으면 규칙만)"""
    p = extract_rules(text)
    return merge(text.strip(), p, ask_llm(text.strip()))


if __name__ == "__main__":
    t = "작년에 강남구 역삼동에서 하던 PT샵을 정리했고, 이번엔 서초구에서 필라테스 스튜디오를 새로 시작하려고 합니다. 만 35세입니다."
    print(json.dumps(extract(t), ensure_ascii=False, indent=1))
