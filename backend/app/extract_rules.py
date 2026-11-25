"""
사용자 문장 -> 프로필 (규칙만, API 안 씀)
업종 · industry · need는 단어로 1차만 잡고 LLM이 보완함
기준일 2026-10-16
"""
import csv, re
from pathlib import Path

DATA = Path(__file__).parent / "data"
YEAR = 2026
BASE_MONTH = 10                          # 기준일 2026-10-16
SEOUL = "서울특별시"


def _read(name):
    with open(DATA / name, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# 동 -> 구 (법정동 · 행정동 코드표)
DONG = {}
for r in _read("dong_gu.csv"):
    DONG.setdefault(r["동"], set()).add(r["구"])
GU = sorted({g for gs in DONG.values() for g in gs})

# 서울 밖 시군구 (법정동 코드표)
OUTSIDE = {}
for r in _read("sigungu.csv"):
    OUTSIDE.setdefault(r["시도"], set()).add(r["시군구"])
SIDO_SHORT = {"경기": "경기도", "인천": "인천광역시", "부산": "부산광역시", "대구": "대구광역시", "대전": "대전광역시",
              "울산": "울산광역시", "세종": "세종특별자치시", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
              "전북": "전북특별자치도", "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도",
              "광주": "전남광주통합특별시", "전남": "전남광주통합특별시",
              # 예전 이름 -> 지금 이름 (광주 · 전남 26.6.30 통합)
              "광주광역시": "전남광주통합특별시", "전라남도": "전남광주통합특별시", "강원도": "강원특별자치도",
              "전라북도": "전북특별자치도", "제주도": "제주특별자치도"}
for full in OUTSIDE:
    SIDO_SHORT[full] = full

# 동네 별칭 -> 구
ALIAS = {"홍대": "마포구", "연남": "마포구", "합정": "마포구", "망원": "마포구", "상수": "마포구", "성수": "성동구",
         "왕십리": "성동구", "이태원": "용산구", "해방촌": "용산구", "신촌": "서대문구", "건대": "광진구", "잠실": "송파구",
         "여의도": "영등포구", "문래": "영등포구", "강남역": "강남구", "압구정": "강남구", "가로수길": "강남구",
         "을지로": "중구", "명동": "중구", "대학로": "종로구", "혜화": "종로구", "북촌": "종로구", "익선": "종로구",
         "서울대입구": "관악구", "샤로수길": "관악구", "노량진": "동작구", "목동": "양천구", "마곡": "강서구",
         "상암": "마포구", "구디": "구로구", "가디": "금천구",
         "구로디지털단지": "구로구", "가산디지털단지": "금천구"}

# 업종 단어 -> 카테고리 (판정 업종 표 기준)
INDUSTRY_WORDS = [
    ("식품 제조·농식품", r"잼|수제 식품|식품|간식|농산물|농식품|소스|김치|브랜드"),
    ("음식·카페", r"카페|커피|디저트|베이커리|베이글|브런치|빵|음식점|식당|한식|중식|일식|양식|분식|떡볶이|치킨|피자|"
                 r"술집|주점|도시락|쿠키|푸드트럭"),
    ("도소매·판매", r"쇼핑몰|소품 ?가게|소품샵|꽃집|서점|옷가게|의류|편의점|마트|용품|도매|소매|스토어|반찬|문구점|문구 ?가게|문방구"),
    ("생활 서비스", r"네일|미용|헤어|세탁|세차|수선|피트니스|헬스|필라테스|요가|대여|청소|수리|돌봄"),
    ("공방·제조", r"공방|도자기|핸드메이드|액세서리|가구|목공|화장품|인쇄|제조"),
    ("IT·소프트웨어", r"(?<!웹)(?<![가-힣])앱|웹(?!툰)|소프트웨어|플랫폼|\bIT\b|AI 서비스|개발 외주|핀테크|블록체인"),
    ("디자인·콘텐츠", r"디자인|스튜디오|콘텐츠|영상|유튜브|웹툰|브랜딩|UX|사진|출판"),
    ("첨단기술", r"딥테크|바이오|반도체|모빌리티|로봇|드론|에너지|기후|물산업"),
    ("기타", r"임대|부동산|원룸"),
]
# 만들어서 팔면 도소매·판매도 같이 (판정 규칙). 팔찌 · 팔로워는 빼기
SELL = r"팔(?!찌|로우|로워|꿈치)|파는|판매|온라인으로|스마트스토어|온라인몰|쇼핑몰"

# need 단어. SURE는 어디 있어도, SOFT는 바라는 말(싶 · 필요 등) 있는 문장에서만
NEED_SURE = [
    ("자금", r"자금|대출|융자|투자|펀딩|보조금|바우처"),
    ("교육·컨설팅", r"교육|컨설팅|상담|멘토|코칭|자문"),
    ("홍보·판매", r"홍보|마케팅|판로|입점|라이브커머스|홈쇼핑|박람회"),
    ("인력", r"채용|인건비|인력|직원.{0,6}(뽑|구하)"),
    ("기술개발", r"기술 ?개발|R&D|연구개발|시제품|특허|지식재산"),
    ("해외진출", r"해외|수출|아마존|글로벌"),
    ("제도·인증", r"인증|확인서"),
]
NEED_SOFT = [
    ("자금", r"돈|부족"),
    ("교육·컨설팅", r"봐주|조언|배우"),
    ("공간·시설", r"공간|작업실|사무실|매장이 필요|매장을 (구|찾)|(제조|작업|만들)할 곳|장소"),
    ("홍보·판매", r"판매|팔아|팔고 싶|알리|손님|단골"),
]
WANT = r"싶|필요|원해|고민|부족|좋겠|있나요|있을까요|받고|해보|려는데|려고"

SPECIAL = [("장애인", r"장애(?![^.,]{0,10}(고용|채용|고객|손님|대상|전용|위한))"), ("국가유공자", r"국가유공자(?! ?가족)"), ("대학생", r"(대학생|대학원생)(?!\s*(대상|손님|고객|상대|들 ?대상))|재학|대학교?\s*\d\s*학년"),
           ("경력단절여성", r"경력.{0,3}(끊|단절)|경단녀"), ("북한이탈주민", r"북한이탈|탈북"), ("다문화가족", r"다문화")]

KNUM = {"스물": 20, "서른": 30, "마흔": 40, "쉰": 50, "예순": 60}
KONE = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9}


def _place(sido=None, gu=None, raw=None, cand=None):
    return {"시도": sido, "시군구": gu, "원문": raw, "후보_구": cand}


# ---- 나이 ----
LATER = r"(내년이면|내년에|곧)\s*(만\s*)?$"     # "내년이면 마흔" -> 지금 나이 아님


def _now(t, pat):
    for m in re.finditer(pat, t):
        if not re.search(LATER, t[:m.start()]):
            return m
    return None


def get_age(t):
    m = re.search(r"(\d{2}|\d{4})\s*년생", t)
    if m:
        y = int(m.group(1))
        y = y if y > 1900 else (2000 + y if y <= YEAR % 100 else 1900 + y)
        return YEAR - y
    m = _now(t, r"(?:만\s*)?(\d{1,2})\s*(?:세|살)")
    if m:
        return int(m.group(1))
    m = _now(t, r"(스물|서른|마흔|쉰|예순)\s*(한|두|세|네|다섯|여섯|일곱|여덟|아홉)?\s*(?:살|이고|이에요|이예요|입니다|이야|인데)")
    if m:
        return KNUM[m.group(1)] + KONE.get(m.group(2), 0)
    return None          # 30대 초반 같은 건 null


# ---- 지역 ----
def _mentions(t):
    """지역 표현 -> [시작, 끝, place]"""
    out = []
    gu_re = "|".join(sorted(GU, key=len, reverse=True))
    for m in re.finditer(rf"(?<![가-힣])({gu_re})", t):
        out.append([m.start(), m.end(), _place(SEOUL, m.group(1), m.group(1))])
    for m in re.finditer(r"(?<![가-힣])([가-힣]{1,5}?\d*(?:동|로)(?:\d가)?)(?=[^가-힣]|에|에서|이|은|쪽|근처|$)", t):
        name = re.sub(r"\d+가$", "", m.group(1))
        gus = DONG.get(name) or DONG.get(re.sub(r"\d+동$", "동", name))
        if gus:
            gs = sorted(gus)
            out.append([m.start(), m.end(), _place(SEOUL, gs[0] if len(gs) == 1 else None, m.group(1),
                                                   None if len(gs) == 1 else gs)])
    for a, g in ALIAS.items():
        for m in re.finditer(rf"(?<![가-힣]){a}(\s?(근처|쪽|부근))?", t):
            out.append([m.start(), m.end(), _place(SEOUL, g, m.group(0))])
    sido_re = "|".join(sorted(SIDO_SHORT, key=len, reverse=True))
    for m in re.finditer(rf"({sido_re})\s*([가-힣]+?)(?:시|군)?(?=에|에서|으로|로|\s|$)", t):
        sido = SIDO_SHORT[m.group(1)]
        hit = [s for s in OUTSIDE[sido] if s.startswith(m.group(2))]
        out.append([m.start(), m.end(), _place(sido, hit[0] if hit else None, m.group(0))])
    out.sort(key=lambda x: (x[0], -x[1]))
    merged = []                          # 붙어 있으면 하나로 (용산구 이태원)
    for s, e, p in out:
        if merged and s <= merged[-1][1] + 1:
            last = merged[-1]
            last[1] = max(last[1], e)
            last[2]["원문"] = t[last[0]:last[1]]
            continue
        merged.append([s, e, p])
    return merged


def get_places(t):
    """-> 거주지, 사업장 (예정지인지 소재지인지는 단계 보고 나눔)"""
    res, biz = None, None
    for s, e, p in _mentions(t):
        after, before = t[e:e + 10], t[max(0, s - 8):s]
        if re.match(r"\s*(에|에서)?\s*(살다가|살았)", after):
            continue                     # 예전에 살던 곳
        if re.match(r"\s*(에|에서|로)?\s*(살|사는|사네|삽니|산다|거주|자취|이사)", after) or "거주지" in before:
            res = res or p
        else:
            biz = biz or p
    return res, biz


# ---- 창업단계 ----
NOT_BIZ = r"(다닌|근무한|일한|온|산|살았던) 지\s*\d+\s*(년|개월)\S*|(회사|직장)\S*\s*\d+\s*(년|개월)\S*"


def _biz(t):
    """회사 다닌 지 10년 같은 사업 아닌 기간 지우기"""
    return re.sub(NOT_BIZ, " ", t)


def get_stage(t):
    t = _biz(t)
    if re.search(r"폐업|접고|그만뒀|문을 닫", t) and not re.search(r"회사를 그만", t):
        return "예비창업"
    if re.search(r"예비\s?창업", t):
        return "예비창업"
    if re.search(r"(연|운영한|개업한|창업한|세운|차린|한) 지|\d+\s*(년|개월)\s*(됐|째|차|했|된)|(?<!준비|생각|계획|거주|공부|고민)하고\s*있"
                 r"|팔고 있|운영\s?(하는|중|하고)|하는 개인사업자|개인\s?\S*사업자(예요|로|이고|입니다)|법인.{0,6}(만들었|세웠|설립)"
                 r"|대표예요|문을? 연|오픈한|개업했|개업한(?!\s*(후|뒤|다음|다면))|열었어|법인(이에요|입니다|이고)", t):
        return "초기창업"
    if re.search(r"준비|려고|려는|예정|싶|생각|계획|등록 전|하려|오픈할|열 ", t):
        return "예비창업"
    return None


# ---- 업력 ----
def get_months(t):
    t = _biz(t)
    m = re.search(r"(올해|작년|재작년|20\d{2}년)\s*(\d{1,2})월[^.,]{0,8}(문을? 연|열었|개업|오픈|시작|창업)", t)
    if m:
        back = {"올해": 0, "작년": 1, "재작년": 2}.get(m.group(1))
        if back is None:
            back = YEAR - int(m.group(1)[:4])
        return back * 12 + (BASE_MONTH - int(m.group(2)))
    if re.search(r"지난\s?달|이번\s?달", t) and re.search(r"등록|개업|오픈|열었|문을? 연|시작|창업", t):
        return 0 if re.search(r"이번\s?달", t) else 1
    m = re.search(r"(\d+)\s*년\s*(\d+)\s*개월", t)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    m = re.search(r"(\d+)\s*개월", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(?<!\d)(\d{1,2})\s*년(?!생)(\s*반)?", t)
    if m:
        return int(m.group(1)) * 12 + (6 if m.group(2) else 0)   # 1년 반 -> 18
    if re.search(r"막 (만들|열|개업|창업)", t):
        return 0
    return None


# ---- 업종 ----
def get_industry(t):
    hits = []
    for cat, pat in INDUSTRY_WORDS:
        for m in re.finditer(pat, t):
            if cat == "식품 제조·농식품" and m.group(0) == "브랜드" and not re.search(r"잼|간식|디저트|식품", t):
                continue
            hits.append((m.start(), m.end(), cat))
    if not hits:
        return None, None
    hits.sort()
    cats = list(dict.fromkeys(c for _, _, c in hits))[:2]
    if cats[0] in ("공방·제조", "식품 제조·농식품") and len(cats) == 1 and re.search(SELL, t):
        cats.append("도소매·판매")
    s, e, _ = hits[0]
    # 원문 = 앞 수식어 + 단어, 조사 떼기
    s -= len(re.search(r"[가-힣A-Za-z]*$", t[:s]).group(0))
    left = re.search(r"(?<![\d가-힣A-Za-z])([가-힣A-Za-z]+)\s$", t[max(0, s - 8):s])
    if left and not re.search(r"(에서|에|를|을|이|가|는|은|고|요|로|도|구|동|살|세|된|한|던|인)$", left.group(1)):
        s -= len(left.group(0))
    e += len(re.match(r"[가-힣A-Za-z]*", t[e:]).group(0))
    raw = re.sub(r"(을|를|이|가|은|는|으로|로|에서|에|도|이고|이에요|예요|하는|입니다)$", "", t[s:e]).strip()
    return cats, raw or None


# ---- need ----
def get_need(t):
    hits = []
    for need, pat in NEED_SURE:
        m = re.search(pat, t)
        if m:
            hits.append((m.start(), need))
    pos = 0
    for sent in re.split(r"(?<=[.?!])\s*", t):
        if re.search(WANT, sent):
            for need, pat in NEED_SOFT:
                m = re.search(pat, sent)
                if m:
                    hits.append((pos + m.start(), need))
        pos += len(sent) + 1
    needs = list(dict.fromkeys(n for _, n in sorted(hits)))[:2]
    return needs or None


# ---- 전체 ----
def extract_rules(text):
    t = text.strip()
    stage = get_stage(t)
    res, biz = get_places(t)
    cats, raw = get_industry(t)
    btype = "개인사업자" if re.search(r"개인\s?\S*사업자|사업자(는|를)?\s*개인", t) else "법인" if "법인" in t else None
    who = r"(?!\s*(고객|손님|대상|전용|분들|용품))"        # 여성 고객 대상 -> 성별 아님
    gender = "여성" if re.search(r"(여성|여자)" + who, t) else "남성" if re.search(r"(남성|남자)" + who, t) else None
    spec = [s for s, pat in SPECIAL if re.search(pat, t)] or None
    p = {"만나이": get_age(t), "거주지": res or _place(),          # 서울 밖 거주도 받음
         "창업단계": stage, "창업예정지": _place(), "사업장소재지": _place(), "업력_개월": None,
         "업종": cats, "사업자_형태": btype, "성별": gender, "특수자격": spec,
         "industry": raw, "need": get_need(t)}
    pre = stage != "초기창업"
    if biz:
        p["창업예정지" if pre else "사업장소재지"] = biz
    if stage == "예비창업":
        p["업력_개월"] = 0
    elif stage == "초기창업":
        p["업력_개월"] = get_months(t)
    p["되묻기_유도"] = ask_fields(p)
    return p


def ask_fields(p):
    """빠진 정보 목록. 없으면 null"""
    pre = p["창업단계"] != "초기창업"
    ask = []
    if p["만나이"] is None: ask.append("만나이")
    def no_gu(x):      # 모르거나, 서울인데 구를 모름 (삼성동 -> 강남 · 관악). 서울 밖은 시도만 알면 됨
        return x["시도"] is None or (x["시도"] == SEOUL and x["시군구"] is None)
    if no_gu(p["거주지"]): ask.append("거주지")
    if pre and no_gu(p["창업예정지"]): ask.append("창업예정지")
    if not pre and no_gu(p["사업장소재지"]): ask.append("사업장소재지")
    if not pre and p["업력_개월"] is None: ask.append("업력_개월")
    if not p["업종"]: ask.append("업종")
    if not p["need"]: ask.append("need")
    return ask or None


if __name__ == "__main__":
    import json
    for s in ["만 28세고 망원동 살아요. 성수동에서 베이글 가게 열려고 준비 중이에요. 인테리어 자금이 필요해요.",
              "신사동에 사는 32살이에요. 꽃집을 차리고 싶어요.",
              "만 34세, 서울 강서구에 살아요. 경기도 부천에서 공방을 운영한 지 3년 차예요."]:
        print(s); print(json.dumps(extract_rules(s), ensure_ascii=False), "\n")
