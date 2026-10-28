"""OFFLINE diagnostic baseline, not LLM/AI. Never use as proof of AI quality.

This is useful for checking JSON shape and evaluate.py without an API key.
"""
from __future__ import annotations
import re
from .schema import empty_result, Place
from .normalization import SEOUL_GU, NEIGHBORHOODS, normalize_result

INDUSTRIES=[
 ('반려동물 용품 쇼핑몰',['G']),('수제 액세서리 온라인 판매',['G']),
 ('수제 쿠키 가게',['I']),('떡볶이 가게',['I']),('핸드메이드 소품',['C','G']),
 ('브런치 카페',['I']),('디저트 카페',['I']),('디저트 브랜드',['C','G']),
 ('한복 대여점',['N']),('디자인 스튜디오',['M']),('독립서점',['G']),
 ('수제 잼',['C']),('소품 가게',['G']),('네일숍',['S']),
 ('치킨집',['I']),('분식집',['I']),('반찬가게',['I']),('미용실',['S']),
 ('꽃집',['G']),('음식점',['I']),('카페',['I']),('앱 서비스',['J']),
 ('AI 서비스',['J']),
]


def demo_extract(text: str, *, user_id: str | None = None) -> dict:
    """Rules only: visible offline sample, NEVER pretends that an LLM was called."""
    if not text.strip():raise ValueError('빈 문장입니다')
    r=empty_result();p=r.사용자프로필;s=r.검색정보;e=r.추가추출값
    m=re.search(r'(?:만\s*)?(\d{1,3})\s*(?:살|세)',text)
    if m:e.나이_언급=int(m.group(1))
    if '여성' in text:p.성별='여성';p.특수자격=['여성']
    if '남성' in text:p.성별='남성'
    # Schema v0.4 section 4: stage, legal form, registration status and
    # historical registration are NOT interchangeable.
    # Q02 '창업 자금을 모아보고 싶다' -> inferred pre-start stage for the
    # provided search-question gold labels; it does NOT prove no prior registration.
    operating = re.search(
        r'운영(?:하고\s*있|한\s*지|\s*중|해요|합니다)|'
        r'(?:가게|카페|사업|법인|회사).{0,8}(?:연\s*지|세운\s*지|설립했)|'
        r'(?:가게|카페|법인).{0,8}(?:열었|차렸|만들었|세웠)|'
        r'(?:가게|카페).{0,7}하는\s*(?:개인사업자|법인)|'
        r'창업(?:한\s*지|을\s*했)|개업했|'
        r'(?<!아직\s)사업자\s*등록(?:을)?\s*했|'
        r'팔고\s*있|사업을\s*하고\s*있|음식점을\s*하고\s*있',text
    )
    preparing = re.search(
        r'예비창업|창업\s*(?:준비|예정|전)|'
        r'창업을?\s*(?:준비|하려|하고|해보고)|창업하고\s*싶|'
        r'열\s*(?:예정|계획|거예요|려|고\s*싶)|'
        r'차리(?:려|고)|준비\s*중|창업팀으로.*운영해보고|'
        r'(?:가게|카페|법인|회사를?)\s*(?:만들|세우)고\s*싶',text
    )
    preparing_funds = re.search(
        r'창업\s*자금(?:을)?\s*(?:모아보고|모으고|마련하고|확보하고)\s*싶',text
    )
    if operating:
        e.창업단계_언급='개업'
    elif preparing or preparing_funds:
        e.창업단계_언급='예비'

    # The user's future intent to incorporate does not mean they have a company.
    # Only an existing corporation / sole proprietorship is a known business type.
    form_existing_corp = re.search(
        r'법인\s*(?:사업자|세운\s*지|설립했|설립한|만들었|세웠|운영\s*중)|'
        r'법인을?\s*(?:막\s*)?(?:만들었|세웠|설립했)',text
    )
    form_existing_personal = re.search(
        r'개인사업자(?:로|로서|입니다|예요|인데|다)',text
    ) and not re.search(r'개인사업자로\s*(?:창업|등록|개업).*?(?:싶|예정|계획)',text)
    if form_existing_corp:
        p.기업형태='법인';p.사업자이력='현재보유';e.현재사업자등록상태='등록'
    elif form_existing_personal:
        p.기업형태='개인사업자';p.사업자이력='현재보유';e.현재사업자등록상태='등록'

    # Registration status refers to NOW. History includes past closed businesses.
    explicit_unregistered = re.search(
        r'사업자\s*등록\s*(?:전|이전)|'
        r'사업자\s*등록(?:은|을)?\s*아직\s*(?:안|못)|'
        r'아직\s*사업자\s*등록(?:을)?\s*(?:안|못|전)|'
        r'미등록',text
    )
    no_history = re.search(
        r'사업자\s*(?:등록\s*)?(?:이력|등록한\s*적)\s*(?:이\s*)?(?:전혀\s*)?(?:없|없어)|'
        r'사업자\s*등록을?\s*한\s*적이?\s*(?:없|없어)',text
    )
    prior_closed = re.search(r'예전에\s*폐업|과거에\s*폐업|폐업한\s*적|폐업\s*이력|이전에\s*폐업|폐업했',text)
    if explicit_unregistered:
        e.현재사업자등록상태='미등록'
        # No legal form is proved by simply saying not-yet registered.
        if not (form_existing_personal or form_existing_corp):p.기업형태=None
    if no_history and not prior_closed and e.현재사업자등록상태!='등록':
        p.사업자이력='없음'
    elif prior_closed and e.현재사업자등록상태!='등록':
        p.사업자이력='폐업'
    # '사업자등록 전' alone does NOT prove 'no registration history ever'.
    m=re.search(r'(?:연\s*지|운영한\s*지|세운\s*지|만든\s*지)\s*(\d+)\s*(개월|달|년)',text)
    if not m:m=re.search(r'(\d+)\s*(개월|달|년)\s*(?:됐|된|운영)',text)
    if m:e.업력_개월=int(m.group(1))*(12 if m.group(2)=='년' else 1)
    elif re.search(r'(?:법인|사업체|가게).{0,5}(?:막\s*(?:만들|설립|차렸))',text):e.업력_개월=0
    if re.search(r'1인|직원\s*없이|혼자\s*차리',text):e.기업규모_표현='1인'
    if re.search(r'직원\s*없이|직원을\s*처음\s*뽑',text):p.상시근로자수=0;e.기업규모_표현='1인'
    m=re.search(r'(\d+)\s*천\s*만\s*원',text)
    if m:e.자금_언급_원=int(m.group(1))*10000000
    # Context-sensitive: find one explicit district or a known neighborhood.
    location_hits=[]
    for gu in SEOUL_GU:
        for match in re.finditer(re.escape(gu),text):location_hits.append((match.start(),gu))
    for nick,gu in NEIGHBORHOODS.items():
        for match in re.finditer(re.escape(nick),text):location_hits.append((match.start(),gu))
    location_hits.sort()
    # Prohibit guessing a borough from several conflicting locations without clear roles.
    for pos,gu in location_hits:
        before=text[max(0,pos-20):pos];after=text[pos:pos+38]
        place=Place(시도='서울특별시',권역=None,시군구=gu)
        if re.search(r'(?:살고|거주|살아요|사는|거주하는|집이)',after):p.거주지=place
        elif re.search(r'(?:운영|하고\s*있|사업장|영업|음식점을\s*하고)',after) and e.창업단계_언급=='개업':p.사업장소재지=place
        elif e.창업단계_언급=='예비':p.창업예정지=place
        elif e.창업단계_언급=='개업':p.사업장소재지=place
    # If the only location mentioned is a residential one, avoid fabricating the place of business.
    # industry: the demo recognizes a few fixed literal patterns only.
    for industry,codes in INDUSTRIES:
        if industry in text:
            s.업종원문표현=industry;p.업종=codes;break
    if '수제 액세서리' in text and ('온라인' in text or '쇼핑몰' in text):
        s.업종원문표현='수제 액세서리 온라인 판매';p.업종=['G']
    need=[];kw=[];situation=[]
    def add(category: str, *words: str):
        if category not in need:need.append(category)
        kw.extend(words)
    if re.search(r'해외\s*쇼핑몰|해외\s*플랫폼|아마존|수출',text):
        add('해외진출','해외 온라인 플랫폼 입점')
    elif re.search(r'크라우드펀딩|자금|대출|돈이\s*부족|융자|투자\s*유치|지원금|돈이\s*모자라',text):
        add('자금',*(['크라우드펀딩'] if '크라우드펀딩' in text else ['창업자금'] if '창업' in text else ['운영자금']))
    if re.search(r'홈쇼핑|라이브커머스|동네\s*사람들한테|가게를\s*알리|손님을\s*어떻게\s*모|온라인\s*판매|다른\s*방법으로.*팔|매출\s*감소',text):
        if '라이브커머스' in text:add('홍보·판매','라이브커머스','온라인 판매')
        elif '홈쇼핑' in text:add('홍보·판매','홈쇼핑 입점')
        elif '온라인' in text:add('홍보·판매','온라인 판매')
        elif '다른 방법으로' in text:add('홍보·판매','판로개척','온라인 판매')
        else:add('홍보·판매','홍보','마케팅')
    if re.search(r'상담|컨설팅|교육|옆에서\s*봐|멘토링',text):
        if '옆에서' in text:add('교육·컨설팅','멘토링','컨설팅')
        elif '교육' in text:add('교육·컨설팅','창업 교육')
        else:add('교육·컨설팅','컨설팅')
    if re.search(r'제조할\s*곳|매장이\s*필요|제조\s*공간|공유주방|입주공간',text):
        if '제조' in text:add('공간·시설','공유주방','제조 공간')
        else:add('공간·시설','창업 공간')
    if re.search(r'인건비|직원.*뽑|채용\s*지원',text):add('인력','인건비 지원','채용 지원')
    if re.search(r'기술\s*개발\s*지원|R&D\s*지원',text):add('기술개발','기술개발','R&D')
    if re.search(r'손님이\s*줄|매출이\s*줄|매출\s*감소',text):situation.append('매출 감소')
    if re.search(r'돈이\s*부족|자금이\s*부족',text):situation.append('자금 부족')
    s.필요지원=need or ['미지정'];s.필요지원키워드=kw;s.상황키워드=situation
    return normalize_result(text,r,user_id=user_id).model_dump(mode='json')
