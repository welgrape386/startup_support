"""Fail-closed normalization: do not invent unknown regions or missing attributes."""
from __future__ import annotations
import re
from .schema import ExtractionResult, Place

SEOUL_GU = (
    '강남구','강동구','강북구','강서구','관악구','광진구','구로구','금천구','노원구',
    '도봉구','동대문구','동작구','마포구','서대문구','서초구','성동구','성북구',
    '송파구','양천구','영등포구','용산구','은평구','종로구','중구','중랑구',
)
SEOUL_SET=set(SEOUL_GU)
# Non-exhaustive, unambiguous aliases. Unknown/ambiguous dongs are NOT guessed.
NEIGHBORHOODS={
    '이태원':'용산구','이태원동':'용산구','한남동':'용산구','후암동':'용산구',
    '연남동':'마포구','합정동':'마포구','망원동':'마포구','홍대':'마포구','서교동':'마포구',
    '잠실동':'송파구','석촌동':'송파구','성수동':'성동구','왕십리':'성동구',
    '혜화동':'종로구','삼청동':'종로구','안암동':'성북구',
    '압구정동':'강남구','역삼동':'강남구','도곡동':'강남구',
    '여의도':'영등포구','여의도동':'영등포구','노량진동':'동작구',
    '신림동':'관악구','봉천동':'관악구','공릉동':'노원구',
    '청담동':'강남구','가산동':'금천구','독산동':'금천구',
}
CITY_ALIASES={
 '서울':'서울특별시','서울시':'서울특별시','서울특별시':'서울특별시',
 '경기':'경기도','경기도':'경기도','인천':'인천광역시','인천광역시':'인천광역시',
 '부산':'부산광역시','부산광역시':'부산광역시','대구':'대구광역시',
 '대전':'대전광역시','광주':'광주광역시','울산':'울산광역시',
 '세종':'세종특별자치시','제주':'제주특별자치도',
 '강원':'강원특별자치도','충북':'충청북도','충남':'충청남도',
 '전북':'전북특별자치도','전남':'전라남도',
 '경북':'경상북도','경남':'경상남도',
}
NEED_CATEGORIES={'자금','교육·컨설팅','공간·시설','홍보·판매','인력','기술개발','해외진출','제도·인증','기타'}
NEED_ALIASES={'홍보':'홍보·판매','마케팅':'홍보·판매','판매':'홍보·판매','컨설팅':'교육·컨설팅','교육':'교육·컨설팅','공간':'공간·시설','기술 개발':'기술개발','해외':'해외진출'}

def _clean_str(s: str | None) -> str | None:
    return s.strip() or None if s is not None else None

def normalize_gu(raw: str | None, sido: str | None=None) -> str | None:
    if raw is None: return None
    t=raw.strip().replace('서울특별시','').replace('서울시','').strip()
    t=re.sub(r'^(?:서울)\s+', '', t)
    # For non-Seoul locality, don't rewrite similarly named "강서구" as a Seoul borough.
    non_seoul = sido not in (None,'서울특별시','서울시','서울')
    if t in SEOUL_SET: return t
    if not non_seoul:
        if t in (x[:-1] for x in SEOUL_GU): return t+'구'
        if t in NEIGHBORHOODS: return NEIGHBORHOODS[t]
        if t.endswith('에서') and t[:-2] in NEIGHBORHOODS: return NEIGHBORHOODS[t[:-2]]
    # Let unambiguous non-Seoul cities/districts pass; unknown Seoul names fail closed.
    if non_seoul and re.fullmatch(r'[가-힣]{2,8}(?:시|군|구)',t): return t
    return None

def normalize_place(place: Place | None) -> Place | None:
    if place is None: return None
    city=_clean_str(place.시도)
    city=CITY_ALIASES.get(city,city)
    district=normalize_gu(place.시군구,city)
    if district in SEOUL_SET and city is None:city='서울특별시'
    if city=='서울특별시' and place.시군구 and not district:
        # Unsupported neighborhood/ambiguous district is not retained as a false filter.
        district=None
    if city is None and district is None and not place.권역: return None
    return Place(시도=city,권역=_clean_str(place.권역),시군구=district)

def normalize_result(text: str, result: ExtractionResult, user_id: str | None=None) -> ExtractionResult:
    # Deep-copy, so caller's parsed result stays intact.
    r=result.model_copy(deep=True)
    p=r.사용자프로필;s=r.검색정보;e=r.추가추출값
    if user_id is not None: p.사용자ID=user_id
    for k in ('거주지','창업예정지','사업장소재지'):
        setattr(p,k,normalize_place(getattr(p,k)))
    p.업종=list(dict.fromkeys(p.업종))[:2]
    p.보유요건=list(dict.fromkeys(x.strip() for x in p.보유요건 if x.strip()))
    p.특수자격=list(dict.fromkeys(x.strip() for x in p.특수자격 if x.strip()))
    p.제외해당=list(dict.fromkeys(x.strip() for x in p.제외해당 if x.strip()))
    cat=[]
    for c in s.필요지원:
        c=NEED_ALIASES.get(c,c)
        if c in NEED_CATEGORIES and c not in cat:cat.append(c)
    s.필요지원=cat if cat else ['미지정']
    s.필요지원키워드=list(dict.fromkeys(x.strip() for x in s.필요지원키워드 if x.strip()))[:8]
    s.상황키워드=list(dict.fromkeys(x.strip() for x in s.상황키워드 if x.strip()))[:8]
    s.업종원문표현=_clean_str(s.업종원문표현)
    if e.나이_언급 is not None and not 0 <= e.나이_언급 <=120:e.나이_언급=None
    if e.업력_개월 is not None and not 0<=e.업력_개월<=1200:e.업력_개월=None
    # Search area must be derived from role-separated location, not hallucinated model field.
    selected=None
    if e.창업단계_언급=='예비':selected=p.창업예정지 or p.거주지
    elif e.창업단계_언급=='개업':selected=p.사업장소재지
    # If stage unknown: no unsafe inference about location's role.
    s.검색지역=selected.시군구 if selected else None
    s.검색시도=selected.시도 if selected else None
    return r
