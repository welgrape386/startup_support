"""Conservative local integration demo: REAL 342 announcements, NO invented eligibility.

Keyword retrieval ≠ RAG. No green/yellow/red judgments without extracted conditions.
Results intentionally use '확인 필요' and meta.dataSource='mock', even though
program names and summaries come from the real database.
"""
from datetime import date
import logging
import os
import re
import sys
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.models import Announcement, AnnouncementFile
from app.schemas import SupportMatchRequest
from app.rag_search import search_ranked, TOP_K
from app.condition_text import load_notices, from_judgment

# 주희님 판정 엔진 경로 추가
_JUDGMENT_DIR = Path(__file__).resolve().parents[2] / 'judgment' / 'proposal'
if str(_JUDGMENT_DIR) not in sys.path:
    sys.path.insert(0, str(_JUDGMENT_DIR))

try:
    import rule_judge as _rj
    _CONDS_FOLDER = _JUDGMENT_DIR / 'conds_gold30'
    _DATES_PATH = _JUDGMENT_DIR / 'ann_dates.csv'
    _IND_DICT_PATH = _JUDGMENT_DIR / '업종_사전.csv'
    _rj_conds: dict | None = None
    _rj_dates: dict | None = None
    _rj_dic: dict | None = None
    _rj_ev = _rj.Evidence(None)  # 근거 검증 없이 실행
    log = logging.getLogger(__name__)
    log.info('rule_judge 로드 성공: %s', _JUDGMENT_DIR)
    _RULE_JUDGE_OK = True
except ImportError as _e:
    log = logging.getLogger(__name__)
    log.warning('rule_judge 로드 실패, 판정 없이 계속: %s', _e)
    _RULE_JUDGE_OK = False

if not _RULE_JUDGE_OK:
    log = logging.getLogger(__name__)

# 예은님 조건 JSON 경로 (환경변수로 덮어쓸 수 있음)
_DEFAULT_CONDITIONS_PATH = Path(__file__).resolve().parents[2] / 'backend' / 'data' / 'conditions' / 'conditions_service_v4_업종확장.json'
CONDITIONS_PATH = Path(os.environ.get('CONDITIONS_JSON', _DEFAULT_CONDITIONS_PATH))

_notices: dict | None = None   # None: 아직 안 불러봄

def _load_notices():
    global _notices
    if _notices is not None:
        return _notices
    try:
        _notices = load_notices(CONDITIONS_PATH)
        log.info('조건 JSON 로드 완료: %d건 (%s)', len(_notices), CONDITIONS_PATH)
    except Exception as e:
        log.warning('조건 JSON 로드 실패, 판정 없이 계속: %s', e)
        _notices = {}
    return _notices

LOCAL_DEMO_NOTICE = '실제 공고 검색(단순 키워드) 데모입니다. 공고별 자격 조건 판정 AI가 아직 연결되지 않아 신청 가능 여부는 모두 확인 필요입니다.'


def _load_rj_data():
    """rule_judge 보조 데이터를 1회만 로드한다."""
    global _rj_conds, _rj_dates, _rj_dic
    if _rj_conds is None:
        try:
            _rj_conds = _load_notices()  # service_v4 62건 (conds_gold30 대신)
        except Exception as e:
            log.warning('service_v4 조건 JSON 로드 실패: %s', e)
            _rj_conds = {}
    if _rj_dates is None:
        try:
            _rj_dates = _rj.load_dates(str(_DATES_PATH)) if _DATES_PATH.exists() else {}
        except Exception as e:
            log.warning('ann_dates.csv 로드 실패: %s', e)
            _rj_dates = {}
    if _rj_dic is None:
        try:
            _rj_dic = _rj.load_industry_dict(str(_IND_DICT_PATH)) if _IND_DICT_PATH.exists() else {}
        except Exception as e:
            log.warning('업종_사전.csv 로드 실패: %s', e)
            _rj_dic = {}


def _profile_to_u(profile: dict) -> dict:
    """local_demo profile dict → rule_judge.py 가 기대하는 u dict 변환.

    rule_judge 기대 형태:
      만나이: int | None
      거주지: {"시도": str, "시군구": str | None} | None
      창업단계: "예비창업" | "초기창업" | None
      업력_개월: int | None
      창업예정지: {"시도": ..., "시군구": ...} | None   # 예비창업자
      사업장소재지: {"시도": ..., "시군구": ...} | None  # 초기창업자
      업종: list[str] | None
      industry: str | None
      사업자_형태: "개인사업자" | "법인" | None
      성별: "여성" | "남성" | None
      특수자격: list | None
    """
    def val(key):
        v = profile.get(key)
        if isinstance(v, dict):
            return v.get('value')
        return v

    sido = val('sido')
    sigungu = val('sigungu')
    loc = {'시도': sido, '시군구': sigungu} if sido else None

    biz_stage = val('bizStage')  # "예비창업" or "초기창업" or None
    startup_months = val('startup_months')  # int | None (업력 개월)

    # industryCategory → 판정 엔진 카테고리명으로 정규화
    # 추출기는 이미 정확한 카테고리명을 반환하지만,
    # ProfileChips에서 사용자가 직접 수정할 때 별칭이 들어올 수 있으므로 정규화 유지
    ind_cat = val('industryCategory')
    _CANON = {
        # 사용자가 직접 입력할 수 있는 별칭 → 정식 카테고리명
        '카페': '음식·카페', '커피': '음식·카페', '음식점': '음식·카페', '식당': '음식·카페',
        '음식': '음식·카페', '외식': '음식·카페', '베이커리': '음식·카페',
        'IT': 'IT·소프트웨어', '소프트웨어': 'IT·소프트웨어', '앱': 'IT·소프트웨어',
        '개발': 'IT·소프트웨어', '스타트업': 'IT·소프트웨어', '플랫폼': 'IT·소프트웨어',
        '제조': '공방·제조', '공방': '공방·제조', '핸드메이드': '공방·제조',
        '도소매': '도소매·판매', '소매': '도소매·판매', '쇼핑몰': '도소매·판매',
        '의류': '도소매·판매', '패션': '도소매·판매',
        '디자인': '디자인·콘텐츠', '콘텐츠': '디자인·콘텐츠', '영상': '디자인·콘텐츠',
        '생활서비스': '생활 서비스', '미용': '생활 서비스', '헤어': '생활 서비스',
        '네일': '생활 서비스', '세탁': '생활 서비스', '피트니스': '생활 서비스',
        '농식품': '식품 제조·농식품', '농업': '식품 제조·농식품', '식품': '식품 제조·농식품',
        # 이미 정식 카테고리명인 경우 (identity)
        '음식·카페': '음식·카페', 'IT·소프트웨어': 'IT·소프트웨어', '공방·제조': '공방·제조',
        '도소매·판매': '도소매·판매', '디자인·콘텐츠': '디자인·콘텐츠', '생활 서비스': '생활 서비스',
        '식품 제조·농식품': '식품 제조·농식품', '첨단기술': '첨단기술', '기타': '기타',
    }
    if ind_cat:
        업종 = [_CANON.get(ind_cat, ind_cat)]
    else:
        업종 = None

    ind_text = val('industryText')  # 업종 원문 텍스트

    # 성별
    gender = None
    if '여성' in (profile.get('targetGroups') or []):
        gender = '여성'

    u = {
        '만나이': val('age'),
        '거주지': loc,
        '창업단계': biz_stage,
        '업력_개월': startup_months,
        '창업예정지': loc if biz_stage == '예비창업' else None,
        '사업장소재지': loc if biz_stage == '초기창업' else None,
        '업종': 업종,
        'industry': ind_text,
        '사업자_형태': None,  # local_demo에서 아직 추출 안 함
        '성별': gender,
        '특수자격': None,
    }
    return u


def _profile_to_u_from_extracted(extracted: dict) -> dict | None:
    """AI 추출 결과(extracted)가 있을 때 판정용 u dict를 직접 만든다.
    없거나 실패하면 None 반환 → _profile_to_u(profile) fallback 사용."""
    try:
        ex = extracted.get('추가추출값') or {}
        sd = extracted.get('검색정보') or {}
        rag = extracted.get('_rag') or {}
        stage_raw = ex.get('창업단계_언급') or ''
        stage = '예비창업' if stage_raw == '예비' else ('초기창업' if stage_raw == '개업' else None)
        sido = sd.get('검색시도') or rag.get('sido') or None
        sigungu = sd.get('검색지역') or rag.get('user_gu') or None
        loc = {'시도': sido, '시군구': sigungu} if sido else None
        age = ex.get('나이_언급')
        ind_cat = ex.get('업종_카테고리') or sd.get('업종_카테고리') or None
        업종 = [ind_cat] if ind_cat else None
        return {
            '만나이': age,
            '거주지': loc,
            '창업단계': stage,
            '업력_개월': None,
            '창업예정지': loc if stage == '예비창업' else None,
            '사업장소재지': loc if stage == '초기창업' else None,
            '업종': 업종,
            'industry': sd.get('업종원문표현'),
            '사업자_형태': None,
            '성별': '여성' if ex.get('성별') == '여성' else None,
            '특수자격': None,
        }
    except Exception:
        return None


def _run_judgment(profile: dict, announcements: list, notices: dict, extracted: dict | None = None) -> dict:
    """판정 엔진(주희님 rule_judge.py) 호출 → {pblancId: {signal, condition_texts}} 반환.

    - conds_gold30/ 에 조건 JSON이 있는 공고만 판정한다.
    - 조건 JSON이 없는 공고는 반환 dict에서 빠짐 → ⚪ 확인 필요로 표시된다.
    """
    if not _RULE_JUDGE_OK:
        return {}
    try:
        _load_rj_data()
        # AI 추출 결과가 있으면 더 정확한 판정용 프로필 사용
        u = None
        if extracted is not None:
            row = extracted.get('_row')
            if row is not None:
                try:
                    from user_extract import to_judge_profile
                    u = to_judge_profile(row)
                except Exception:
                    u = None
            if u is None:
                u = _profile_to_u_from_extracted(extracted)
        if u is None:
            u = _profile_to_u(profile)
        result_map = {}
        for a in announcements:
            pid = a.announcement_id
            cond = _rj_conds.get(pid)
            if cond is None:
                # 조건 JSON 없음 → ⚪ 확인 필요로 result_map에 포함
                result_map[pid] = {
                    'pblancId': pid,
                    'signal': '⚪',
                    'condition_texts': [{'label': '확인 필요', 'text': '자격조건 정보가 없어 직접 확인이 필요해요.'}],
                }
                continue
            try:
                sig, res, c, track, cands = _rj.judge_pair(cond, u, pid, _rj_dates, _rj_ev, _rj_dic)
                # from_judgment 형태 맞추기
                raw = {
                    'pblancId': pid,
                    'signal': sig,
                    'stage': u.get('창업단계') or '',
                    'results': {k: v[0] for k, v in res.items()} if res else {},
                    'track': track or None,
                }
                # 업종 추가 정보
                if '업종' in res:
                    ind_v = res['업종'][0]
                    ind_detail = res['업종'][2] if len(res['업종']) > 2 else {}
                    if ind_v == _rj.COND:
                        raw['industry_reason'] = '허용불일치'
                    elif ind_v == _rj.NO:
                        raw['industry_reason'] = '제외'
                    if isinstance(ind_detail, dict):
                        if ind_detail.get('industry_reason'):
                            raw['industry_reason'] = ind_detail['industry_reason']
                        if ind_detail.get('industry_hit'):
                            raw['industry_hit'] = ind_detail['industry_hit']
                # 대안조건 alt_left
                if '대안조건' in res:
                    alt_detail = res['대안조건'][2] if len(res['대안조건']) > 2 else {}
                    if isinstance(alt_detail, dict) and alt_detail.get('alt_left') is not None:
                        raw['alt_left'] = alt_detail['alt_left']
                # user_industry: 사용자 업종 (허용불일치 때 "OO은 해당 안 됨" 문구용)
                if u.get('업종'):
                    raw['user_industry'] = u['업종']
                jmt_out = from_judgment(raw, notices)
                # judgment_results: 조건별 판정 신호 {"사업자등록": "✅", "지역": "🟡", ...}
                # rule_judge 반환 res: {조건명: (신호이모지, ...)} → 첫 번째 요소만 추출
                SIGNAL_MAP = {_rj.OK: '✅', _rj.COND: '🟡', _rj.UNK: '❔', _rj.NO: '❌'}
                jmt_out['judgment_results'] = {
                    k: SIGNAL_MAP.get(v[0], v[0]) for k, v in (res or {}).items()
                }
                result_map[pid] = jmt_out
            except Exception as e:
                log.warning('판정 오류 (%s): %s', pid, e)
                continue
        return result_map
    except Exception as e:
        log.warning('_run_judgment 실패, 확인 필요로 대체: %s', e)
        return {}
REGIONS = [('서울','서울특별시'),('인천','인천광역시'),('경기','경기도'),('부산','부산광역시'),('대구','대구광역시'),('대전','대전광역시'),('광주','광주광역시'),('울산','울산광역시'),('세종','세종특별자치시'),('강원','강원특별자치도'),('충북','충청북도'),('충남','충청남도'),('충청북','충청북도'),('충청남','충청남도'),('전북','전북특별자치도'),('전남','전라남도'),('경북','경상북도'),('경남','경상남도'),('제주','제주특별자치도')]
IGNORE = {'서울','경기','인천','부산','대구','대전','광주','울산','세종','제주','강원','경북','경남','충북','충남','전북','전남','준비','지원','사업','신청','창업','예비창업','하려고','그리고','있어요','해주세요','합니다','부탁해','저는','제가','되어','받고','원해','하려','이제','있는','싶어요','부족해요'}
TYPES = ('융자','보조금','보증','교육','멘토링','공간','사업화','기타')

def _extracted(value, evidence=None):
    return {'value':value,**({'evidence':evidence} if evidence and value is not None else {})}

def get_profile(text: str, overrides: dict | None):
    txt=re.sub(r'\[[^\]]*\]',' ',text)
    m=re.search(r'(?:만\s*)?(\d{2})\s*[살세]',txt)
    age=int(m.group(1)) if m and 14<=int(m.group(1))<=100 else None
    sido=next((s for k,s in REGIONS if k in txt),None)
    sigungu=(re.search(r'([가-힣]{1,6}(?:시|구|군))(?=[에서의은는이가도\s,.]|$)',txt) or [None])[0]
    if sigungu and sigungu in ['서울시','인천시','부산시','대전시','대구시','광주시','울산시','세종시','경기도']:
        sigungu=None
    stage='예비창업' if re.search(r'예비창업|창업\s*전|미창업|창업\s*예정',txt) else None
    if stage is None and re.search(r'(창업|개업)\s*[1-3]\s*년|업력\s*[1-3]\s*년',txt): stage='업력3년이하'
    # 업종 감지: 판정 엔진 카테고리와 동일한 이름으로 직접 반환
    _IND_RULES = [
        ('음식·카페',    r'카페|커피|디저트|베이커리|베이글|브런치|빵|음식점|식당|한식|중식|일식|양식|분식|떡볶이|치킨|피자|술집|주점|도시락|쿠키|푸드트럭'),
        ('식품 제조·농식품', r'잼|수제 식품|식품 제조|간식 제조|농산물|농식품|소스|김치'),
        ('도소매·판매',  r'쇼핑몰|소품 ?가게|소품샵|꽃집|서점|옷가게|의류|편의점|마트|용품|도매|소매|스토어|반찬|문구점|문구 ?가게|문방구'),
        ('생활 서비스',  r'네일|미용|헤어|세탁|세차|수선|피트니스|헬스|필라테스|요가|대여|청소|수리|돌봄'),
        ('공방·제조',    r'공방|도자기|핸드메이드|액세서리|가구|목공|화장품|인쇄|제조'),
        ('IT·소프트웨어', r'(?<!웹)(?<![가-힣])앱 개발|앱을 만|웹 서비스|소프트웨어|플랫폼 개발|\bIT\b|AI 서비스|개발 외주|핀테크|블록체인'),
        ('디자인·콘텐츠', r'디자인|스튜디오|콘텐츠|영상 제작|유튜브|웹툰|브랜딩|UX|사진|출판'),
        ('첨단기술',     r'딥테크|바이오|반도체|모빌리티|로봇|드론|에너지|기후|물산업'),
        ('기타',         r'임대업|부동산'),
    ]
    category = None
    for _cat, _pat in _IND_RULES:
        if re.search(_pat, txt):
            category = _cat
            break
    needs=[]
    if re.search('모자라|부족|자금|대출|지원금|융자',txt): needs+=['융자','보조금']
    for k in ('교육','멘토링','공간','사업화','보증'):
        if k in txt:needs.append(k)
    fund=None
    m_money=re.search(r'(\d+(?:\.\d+)?)\s*억',txt)
    if m_money:fund=round(float(m_money.group(1))*10000)
    else:
        m_money=re.search(r'(\d+(?:\.\d+)?)\s*천\s*만',txt)
        if m_money:fund=round(float(m_money.group(1))*1000)
        else:
            m_money=re.search(r'(\d[\d,]*)\s*만\s*원?',txt)
            if m_money:fund=int(m_money.group(1).replace(',',''))
    o=overrides or {}
    # Frontend ProfileChips sends raw primitives; also accept Extracted-shaped values.
    def override(key, value):
        if key not in o: return value
        val=o[key]
        return val.get('value') if isinstance(val,dict) and 'value' in val else val
    age=override('age',age)
    sido_new=override('sido',sido)
    if sido_new!=sido:sigungu=None
    # The new profile chip editor can replace age; derived groups must use the
    # edited value, not the originally parsed one.
    groups=['청년'] if age is not None and age<=39 else []
    if re.search('소상공인|자영업',txt):groups.append('소상공인')
    if re.search('여성',txt):groups.append('여성')
    profile={
       'age':_extracted(age,'사용자 문장/수정' if age is not None else None),
       'sido':_extracted(sido_new),'sigungu':_extracted(override('sigungu',sigungu)),
       'bizStage':_extracted(override('bizStage',stage)),
       'industryCategory':_extracted(override('industryCategory',category)),
       'industryText':_extracted(None),'targetGroups':groups,'needs':needs,
       'fundingGapManwon':_extracted(fund),'budgetManwon':_extracted(None),
       'experienceYears':_extracted(None),'freeText':text
    }
    missing=[k for k in ('age','sido','bizStage','industryCategory') if profile[k]['value'] is None]
    return profile,missing

def _terms(text):
    terms=re.findall(r'[가-힣A-Za-z0-9]{2,}',text.lower())
    return list(dict.fromkeys(t for t in terms if t not in IGNORE and not t.isnumeric() and len(t)>1))[:18]

def _support_types(a):
    text=f'{a.title} {a.category_large or ""} {a.category_medium or ""} {a.summary or ""}'
    result=[]
    if re.search('융자|대출|정책자금',text):result.append('융자')
    if re.search('보조금|지원금|사업비|사업화자금',text):result.append('보조금')
    if re.search('보증|특례보증',text):result.append('보증')
    if re.search('교육|강좌|아카데미|세미나|교육생',text):result.append('교육')
    if re.search('멘토링|멘토|컨설팅',text):result.append('멘토링')
    if re.search('입주|공유오피스|사무실|창업공간',text):result.append('공간')
    if re.search('사업화|시제품|판로',text):result.append('사업화')
    return list(dict.fromkeys(result)) or ['기타']

def _score(a, terms, profile):
    title=a.title.lower();summary=(a.summary or '').lower();cats=f'{a.category_large or ""} {a.category_medium or ""}'.lower()
    hits_title=sum(t in title for t in terms)
    hits_other=sum(t in summary for t in terms)
    hits_cat=sum(t in cats for t in terms)
    val=hits_title*12+hits_other*3+hits_cat*5
    # Region mentioned is a ranking clue, never an eligibility pass/fail.
    sido=profile['sido']['value'];
    if sido:
        short=next((k for k,s in REGIONS if s==sido),None)
        tagged=re.match(r'^\s*\[([^]]+)\]', a.title)
        if (short and short in a.title) or sido in a.title:val+=14
        elif tagged:
            region_tag=tagged.group(1)
            if any(k in region_tag for k,_ in REGIONS):
                val-=12   # geographic relevance only; not an eligibility exclusion
    for n in profile['needs']:
        if n in _support_types(a):val+=3
    if profile['industryCategory']['value'] and profile['industryCategory']['value'].lower() in title:val+=5
    return max(0,int(val))

EXEC_METHODS = {'직접수행', '위탁수행', '직접 수행', '위탁 수행'}
PLACEHOLDER_ORG = {'기초자치단체'}

def _card_org(a):
    """카드 기관 칸 값. 수행기관이 실제 기관명이면 그대로, 자리표시 값이면 None(주관기관 사용).
    '기초자치단체'는 제목 머리말 [부산] 남구 에서 '부산 남구'를 만든다 (없으면 주관기관)."""
    exe=(a.operator or '').strip()
    if exe and exe not in EXEC_METHODS and exe not in PLACEHOLDER_ORG:
        return exe
    if exe in PLACEHOLDER_ORG:
        m=re.match(r'^\[([^\]]+)\]\s*([^\s\d\[\]]+)', (a.title or '').strip())
        if m: return f"{m.group(1)} {m.group(2)}"
    return None

def _short_summary(text, limit=80):
    """카드용 한 줄 요약. 원문을 바꾸지 않고 머리말만 잘라 쓴다 (☞·※ 안내문 제외). 전체 원문은 상세 fields 에 남긴다."""
    if not text:return ''
    s=re.split(r'[☞※\n]', text, maxsplit=1)[0].strip()
    if len(s)>limit:
        cut=s[:limit]
        s=(cut[:cut.rfind(' ')] if ' ' in cut[20:] else cut).rstrip(' ,.') + '…'
    return s

# 카드 요약: ☞ 줄 두 개(대상 + 지원 내용)가 이 글자 수 안이면 둘 다 보이고, 넘으면 지원 내용 줄만 보인다.
CARD_SUMMARY_MAX = 70

def _card_summary(text):
    """카드용 요약: '☞' 안내 줄만 모은다. 짧으면 전부, 길면 마지막 ☞ 줄(지원 내용)만. ☞ 줄이 없으면 머리말 요약."""
    if not text: return ''
    lines=[]
    for ln in text.splitlines():
        ln=ln.replace('\xa0',' ').strip()
        if ln.startswith('☞'):
            t=ln[1:].strip()
            if t: lines.append(t)
    if not lines: return _short_summary(text)
    whole='\n'.join(lines)
    return whole if len(whole)<=CARD_SUMMARY_MAX else lines[-1]

# 판정 기준일: 공고 데이터 스냅샷 날짜 (팀 회의 결정). 마감 판단을 오늘 날짜가 아니라 이 날짜로 한다
JUDGE_AS_OF = date(2026, 10, 16)

def _is_rolling(a):
    """rolling=1이면 모집 중 취급. '예산 소진시까지'·'상시 접수'·'연중' 모두 포함."""
    return bool(a.rolling)

def _program(a, today):
    raw=a.raw_fields or {}
    fields={
      '공고명':a.title,'사업개요':a.summary or '',
      '지원대상':a.target_name or '',
      '신청기간':a.application_period_raw or '',
      '신청방법':a.application_method or '',
    }
    # Exact source fields available for verification; don't manufacture rule quotes.
    for k,v in raw.items():
        if isinstance(v,str) and v:fields[k]=v
    status = ('마감' if a.apply_end and a.apply_end < today else
              '모집예정' if a.apply_start and a.apply_start>today else
              '모집중' if (a.apply_end or _is_rolling(a)) else '기간 확인 필요')
    files=[{'name':f.file_name or '첨부파일','url':f.file_url} for f in sorted(a.files,key=lambda f:(f.file_role,f.sequence))]
    data={
      'id':a.announcement_id,'source':'bizinfo','portal':'기업마당',
      'sourceId':a.announcement_id,'title':a.title,'agency':a.agency or '기관 정보 미상',
      'supportTypes':_support_types(a),'support_types':a.support_types or [],'rolling':a.rolling,'status':status,
      # 중복지원: DB에 값 있으면 사용, 없으면 미확인
      'duplicatePolicy': a.duplicate_policy_json or {'status':'미확인'},
      'summary':_card_summary(a.summary) or a.title,'url':a.announcement_url or '',
      'fields':fields,'fetchedAt':(a.fetched_updated_at or a.fetched_created_at or today.isoformat())[:10],
      'reviewed':False,'attachmentFiles':files,
    }
    # 카드 기관 칸: 실제 수행기관명이면 수행기관, 아니면 주관기관(agency). 주관기관은 상세 fields 에도 남긴다.
    exe=(a.operator or '').strip()
    org=_card_org(a)
    if org: data['operator']=org
    fields['주관기관']=a.agency or ''
    if exe in EXEC_METHODS: fields['수행방식']=exe
    elif exe and exe not in PLACEHOLDER_ORG: fields['수행기관']=exe
    if a.apply_start:data['applyStart']=a.apply_start.isoformat()
    if a.apply_end:data['applyEnd']=a.apply_end.isoformat()
    if a.contact:data['contact']=a.contact
    if a.application_url:data['applyUrl']=a.application_url
    # 초록색 칸: 원문 추출값 (예은님) - DB에 채워지면 자동 반영
    if a.amount_max_manwon:   data['amountMaxManwon']  = a.amount_max_manwon
    if a.total_budget_text:   data['totalBudgetText']  = a.total_budget_text
    if a.interest_rate:       data['interestRate']     = a.interest_rate
    if a.support_detail:      data['supportDetail']    = a.support_detail
    if a.submission_docs_json:data['submissionDocs']   = a.submission_docs_json
    if a.bonus_points_json:   data['bonusPoints']      = a.bonus_points_json
    if a.rounds_json:         data['rounds']           = a.rounds_json
    # 갈색 칸: 새 필드
    if a.self_funding_json:   data['selfFunding']      = a.self_funding_json
    if a.info_tracks_json:    data['infoTracks']       = a.info_tracks_json
    return data

def get_match_response(request: SupportMatchRequest, session: Session, limit=TOP_K, as_of=None, extracted=None):
    today=as_of or JUDGE_AS_OF
    profile,missing=get_profile(request.text,request.overrides)
    # Keep original UI profile shape; let AI fill available values when enabled.
    ai_terms = ''
    if extracted is not None:
        search = extracted['검색정보']
        extra = extracted['추가추출값']
        user = extracted['사용자프로필']
        def put(key, value):
            if value is not None and not (request.overrides and key in request.overrides):
                profile[key] = _extracted(value, 'AI 추출')
        put('age', extra.get('나이_언급'))
        put('sido', search.get('검색시도'))
        put('sigungu', search.get('검색지역'))
        stage = extra.get('창업단계_언급')
        put('bizStage', '예비창업' if stage=='예비' else '초기창업' if stage=='개업' else None)
        put('industryText', search.get('업종원문표현'))
        # AI 추출 결과에 업종 카테고리가 있으면 채움 (규칙 추출 fallback 보완)
        ai_ind_cat = extra.get('업종_카테고리') or search.get('업종_카테고리')
        if ai_ind_cat and profile.get('industryCategory', {}).get('value') is None:
            put('industryCategory', ai_ind_cat)
        needs = [x for x in search.get('필요지원',[]) if x!='미지정']
        if needs: profile['needs']=needs
        if user.get('성별') == '여성' and '여성' not in profile['targetGroups']:
            profile['targetGroups'].append('여성')
        age = profile['age']['value']
        if age is not None and age <= 39 and '청년' not in profile['targetGroups']:
            profile['targetGroups'].append('청년')
        missing = [k for k in ('age','sido','bizStage','industryCategory') if profile[k]['value'] is None]
        ai_terms = ' '.join([*search.get('필요지원키워드',[]),*search.get('상황키워드',[])])
    terms=_terms(request.text + ' ' + ai_terms)
    announcements=session.scalars(select(Announcement).options(selectinload(Announcement.files))).all()
    # For the demo, show listings with an explicit future close date or explicit all-year receipt.
    # No inference from '예산 소진시까지' that the window is still open.
    active=[]
    for a in announcements:
        # Filter only after a reviewed region_map.csv has populated the columns.
        # Unmapped/unknown region never gets guessed from the title.
        if a.region == '타지역':
            continue
        if a.region == '서울' and profile['sido']['value'] not in (None, '서울특별시', '서울'):
            continue
        if a.seoul_gu and a.seoul_gu.strip():
            allowed_gu = {g.strip() for g in a.seoul_gu.split(',') if g.strip()}
            user_gu = profile['sigungu']['value']
            # Unknown district must not be treated as a known mismatch.
            if user_gu is not None and user_gu not in allowed_gu:
                continue
        if a.apply_end is not None:
            if a.apply_start and a.apply_start>today:continue
            if a.apply_end < today:continue
        elif not a.rolling:
            # apply_end 없고 rolling도 아니면 제외
            # rolling=1이면 period 텍스트('예산 소진시까지', '상시 접수', '연중' 등) 무관하게 포함
            continue
        s=_score(a,terms,profile)
        active.append((s,a))
    active.sort(key=lambda pair:(pair[0], pair[1].apply_end or date.max),reverse=True)
    # RAG 검색 순위가 있으면 그 순서를 쓴다. 자격 판정이 아니라 관련도 순서만 준다.
    # 지역·마감 필터는 위에서 이미 적용된 active 안에서만 고른다. RAG 결과가 없으면 키워드 순서로 간다.
    user_gu = profile['sigungu']['value'] if profile['sido']['value'] in (None, '서울특별시', '서울') else ''
    # 추출 결과가 있을 때만 검색 조건으로 넘긴다. 없으면 빈 값 (그 조건은 검색에서 빠짐)
    sx={}
    if extracted is not None:
        # 나애님 adapter.to_legacy()가 _rag 키로 RAG 인자를 미리 계산해 줌
        if '_rag' in extracted:
            rag_args = extracted['_rag']
            sx = dict(
                stage=rag_args.get('stage', ''),
                need=rag_args.get('need', '').split('|')[0] if rag_args.get('need') else '',
                industry=rag_args.get('industry_cat', '').split('|')[0] if rag_args.get('industry_cat') else '',
                industry_cat=rag_args.get('industry_cat', ''),
                age=rag_args.get('age', ''),
            )
            # _rag.user_gu 가 있으면 프로필에서 뽑은 user_gu 를 덮어씀
            if rag_args.get('user_gu'):
                user_gu = rag_args['user_gu']
        else:
            # 구버전 호환 (기존 schema-v0.4 extracted 형태)
            sd=extracted.get('검색정보') or {}; ex=extracted.get('추가추출값') or {}
            nd=sd.get('필요지원') or []
            sx=dict(stage=ex.get('창업단계_언급') if ex.get('창업단계_언급') in ('예비','개업') else '',
                    need=(nd[0] if isinstance(nd,list) and nd else (nd if isinstance(nd,str) else '')),
                    industry=sd.get('업종원문표현') or '',
                    industry_cat=profile['industryCategory']['value'] or '',
                    age=str(ex.get('나이_언급') or ''))
    rag = search_ranked(request.text, user_gu=user_gu, **sx)
    rag_rank = {r['pblancId']: r for r in rag} if rag else {}
    ranked = sorted([(s, a) for s, a in active if a.announcement_id in rag_rank],
                    key=lambda pair: rag_rank[pair[1].announcement_id]['rank'])
    # 필터 이후 상위 TOP_K개만 판정으로 넘긴다 (RAG는 POOL개를 받아 둠)
    ranked = ranked[:TOP_K]
    # Return meaningful matches, but also allow general requests to see examples.
    if ranked:
        candidates = ranked
    else:
        candidates=[(score,a) for score,a in active if score>0]
        if not candidates:candidates=active
    notices = _load_notices()
    # 판정 엔진 연결 준비: judgment_map은 주희님 판정 결과를 {pblancId: 판정결과} 형태로 받는다.
    # 현재는 판정 엔진이 미연결이므로 빈 dict. 연결 시 아래 _run_judgment()를 구현한다.
    judgment_map = _run_judgment(profile, [a for _,a in candidates[:limit]], notices, extracted=extracted)
    results=[]
    for score,a in candidates[:limit]:
        program=_program(a,today)
        # Score is a *display relevance* score, NOT an eligibility confidence probability.
        percent=max(1,min(80,20+score))
        days=(a.apply_end-today).days if a.apply_end else None
        search_rank = rag_rank[a.announcement_id]['rank'] if a.announcement_id in rag_rank else None
        # 조건 JSON이 있는 공고는 has_conditions=True 표시 (판정 엔진 연결 전 준비)
        has_conditions = a.announcement_id in notices
        # 판정 결과가 있으면 신호등과 condition_texts를 채운다; 없으면 확인 필요로 표시
        jmt = judgment_map.get(a.announcement_id)
        if jmt:
            signal = jmt.get('signal', '⚪')
            # 프론트엔드 MatchVerdict 타입에 맞춰 반환 (types.ts)
            verdict = {'🟢': '자격 충족', '🟡': '조건부', '🔴': '자격 미달', '⚪': '확인 필요'}.get(signal, '확인 필요')
            condition_texts = jmt.get('condition_texts', [])
            # judgmentResults: 조건별 판정 신호 {조건명: "✅"|"🟡"|"❔"|"❌"} - 나애님 judge_p1_gold_v2_detail.json 형식
            judgment_results = jmt.get('judgment_results', {})
            headline = {
                '🟢': '신청 가능 · 확인된 자격조건 충족',
                '🟡': '조건부 가능 · 아래 조건을 확인하세요',
                '🔴': '신청 불가 · 필수 자격조건 미충족',
                '⚪': '확인 필요 · 추가 정보가 필요합니다',
            }.get(signal, '관련 공고 검색됨 · 신청자격 확인 필요')
        else:
            signal = '⚪'
            verdict = '확인 필요'
            condition_texts = []
            judgment_results = {}
            headline = '관련 공고 검색됨 · 신청자격 확인 필요'
        results.append({
          'program':program,'verdict':verdict,'signal':signal,'score':percent,
          'searchScore':float(score),'searchRank':search_rank,'judgmentScore':None,'rules':[],
          'headline':headline,
          'reasons':[],'cautions':[], 'exceptions':[], 'daysLeft':days,
          'hasConditions': has_conditions,
          'conditionTexts': condition_texts,  # 🟡일 때만 값 있음. 나애님 condition_text.py 출력
          'judgmentResults': judgment_results,  # 조건별 판정 신호 {조건명: "✅"|"🟡"|"❔"|"❌"}
        })
    # 🔴 자격 미달은 excluded로, 🟡 조건부는 conditional로 분리
    # 프론트엔드: res.excluded → 해당 안 됨, res.conditional → 조건부 가능
    excluded = []
    conditional = []
    final_results = []
    for r in results:
        if r['signal'] == '🔴':
            excluded.append({
                'programId': r['program']['id'],
                'title': r['program']['title'],
                'failedReasons': r.get('conditionTexts') or [],
                'url': r['program'].get('url'),
                'program': r['program'],
                'result': r,
            })
        elif r['signal'] == '🟡':
            conditional.append(r)
        else:
            final_results.append(r)

    return {
      'profile':profile,'missing':missing,'results':final_results,'conditional':conditional,'excluded':excluded,
      'nextSteps':[],
      'summary':{'eligibleCount':sum(1 for r in final_results if r['signal']=='🟢'),
                 'checkCount':len(final_results) + len(conditional),
                 'conditional':{'bizStage':0,'sigungu':0},'urgent':None,'caution':None},
      'coverage':{'sources':[{'portal':'기업마당','count':len(announcements)}],
                  'total':len(announcements),'asOf':today.isoformat(),'regions':[]},
      'meta':{'dataSource':'live','parser':('schema-v0.4-extraction' if extracted is not None else 'rule'),'indexBuiltAt':today.isoformat(),
              'totalPrograms':len(announcements),'droppedClaims':0},
      # Additive field; current frontend ignores it. Local patched frontend shows its own notice.
      'demoNotice':LOCAL_DEMO_NOTICE,
    }
