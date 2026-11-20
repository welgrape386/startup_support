"""제안 방식: 조건 JSON + 사용자 정보 → 규칙 판정 코드

LLM은 공고에서 자격 조건을 뽑기만 하고(조건 JSON), 판정은 이 코드가 한다.
판정 기준은 '판정규칙 통합'과 '자격조건 스키마 총정리', 업종은 '업종 카테고리 매칭'(업종_사전.csv 규칙)을 따른다.
"""
import argparse
import calendar
import csv
import json
import os
import re
import unicodedata
from collections import Counter
from datetime import date, timedelta

REF_DATE = date(2026, 10, 16)  # 판정 기준일 (고정)
IND_MAP = None


LABELS = {'🟢': '🟢 신청 가능', '🟡': '🟡 조건부가능', '⚪': '⚪️ 확인 필요', '🔴': '🔴 신청 불가'}

# 조건 결과
OK, COND, UNK, WHITE, NO = '✅', '🟡', '❔', '⚪', '❌'
GOOD = {OK: 4, COND: 3, UNK: 2, WHITE: 1, NO: 0}          # 대안조건
SIGNAL_GOOD = {'🟢': 3, '🟡': 2, '⚪': 1, '🔴': 0}           # 트랙

BIZ_TYPES = ('개인사업자', '법인')
PLACE_TYPES = ('사업장소재지', '사업자등록지', '본사소재지', '공장소재지')
HOME_TYPES = ('거주지', '주민등록지')
AGE_TARGETS = (None, '대표자', '신청자_본인', '구성원_전원', '공동대표_전원', '명시없음')
CHECKLIST_KEYS = ('기업규모', '보유요건', '제외대상', '창업이력', '기타조건')
LIST_KEYS = ('특수자격', '대안조건') + CHECKLIST_KEYS
JUDGED_KEYS = {'나이', '성별', '지역', '업력', '사업자등록', '신청자_유형', '업종', '특수자격'}
ORDER = ('사업자등록', '업력', '신청자_유형', '지역', '나이', '성별', '업종', '특수자격', '대안조건')

# 업종 원문 판단표
# '기타' 사용자와 부분 제외는 사용자 업종 원문(industry)으로 공고 업종명에 해당하는지 본다
# (원문 단어들, 공고 업종명에 들어 있는 글자)
RAW_TAGS = [
    (['임대', '부동산'], '부동산'),
    (['숙박', '펜션', '게스트하우스', '모텔', '호텔'], '숙박'),
    (['학원', '교습'], '학원'),
    (['운수', '택시', '화물', '택배'], '운수'),
]
# 카테고리 안에서 갈리는 부분 제외: (공고 업종명 글자, 사용자 카테고리(None이면 전부), 해당 단어, 모를 때 단어)
PARTIAL_EXCL = [
    ('주점', '음식·카페', ['주점', '술집', '호프', '포차', '이자카야'], []),
    ('유흥', '음식·카페', ['유흥', '룸살롱', '나이트'], []),
    ('단순 카페', '음식·카페', [], ['카페']),
    ('안마', '생활 서비스', ['안마', '마사지'], []),
    ('무인', None, ['무인'], []),
    ('프랜차이즈', None, ['프랜차이즈', '가맹'], []),
]
# 제외 업종의 예외("단, ~은 가능")에 들어가는지: in=확실히 들어감, out=확실히 안 들어감, 둘 다 아니면 ❔
EXCEPTION_RULES = {
    '소매업': {'in': ['온라인', '쇼핑몰', '전자상거래', '통신판매'], 'out': []},
    '부동산업': {'in': ['관리', '중개', '분양', '공유오피스', '공유주방'], 'out': ['원룸', '주택', '아파트', '주거']},
}


# 읽기

def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def parse_cell(v):
    """CSV 칸: '' / 'null' → None, JSON 모양이면 파싱, 숫자는 int"""
    v = (v or '').strip()
    if v in ('', 'null', 'None'):
        return None
    if v[0] in '{[':
        return json.loads(v)
    if re.fullmatch(r'-?\d+', v):
        return int(v)
    return v


def load_users(path):
    users = {}
    for r in read_csv(path):
        u = {k: parse_cell(v) for k, v in r.items()}
        if isinstance(u.get('industry'), int):
            u['industry'] = str(u['industry'])
        users[r['사용자ID']] = u
    return users


def load_conds(folder):
    conds = {}
    for name in sorted(os.listdir(folder)):
        if name.startswith('PBLN_') and name.endswith('.json'):
            d = json.load(open(os.path.join(folder, name), encoding='utf-8'))
            conds[d['공고ID']] = d
    return conds


def load_dates(path):
    out = {}
    for r in read_csv(path):
        out[r['공고ID']] = {k: (date.fromisoformat(v) if v else None) for k, v in (('공고일', r['공고일']), ('접수마감일', r['접수마감일']))}
    return out


def load_industry_dict(path):
    d = {}
    for r in read_csv(path):
        split = lambda s: [x for x in (s or '').split('|') if x]
        d[r['업종명'].strip()] = {'허용': split(r['허용_카테고리']), '제외': split(r['제외_카테고리'])}
    return d


# 근거 검증 (원문에서 못 찾은 근거의 조건은 미기재)

def norm_text(s):
    s = unicodedata.normalize('NFKC', s or '')
    return re.sub(r'[\s\'"‘’“”`·•∙ㆍ※*\-–—_()\[\]「」『』<>〈〉《》,.:;]', '', s)


class Evidence:
    def __init__(self, folder):
        self.folder = folder
        self.cache = {}
        self.dropped = []

    def found(self, pid, ev):
        if not self.folder or not ev:
            return True
        if pid not in self.cache:
            p = os.path.join(self.folder, pid + '.txt')
            self.cache[pid] = norm_text(open(p, encoding='utf-8').read()) if os.path.exists(p) else None
        text = self.cache[pid]
        if text is None:
            return True
        return norm_text(ev) in text

    def check(self, pid, where, field):
        """조건 dict 하나. 근거를 못 찾으면 None(미기재)"""
        if not isinstance(field, dict):
            return field
        if self.found(pid, field.get('근거')):
            return field
        self.dropped.append((pid, where, field.get('근거')))
        return None


# 날짜

def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def add_years(d, n):
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return d.replace(year=d.year + n, day=28)


def base_date(pid, 기준일, dates):
    """조건의 기준일 → 실제 날짜. 모르면 판정 기준일"""
    if 기준일 and re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(기준일)):
        return date.fromisoformat(기준일)
    if 기준일 in ('공고일', '접수마감일'):
        return (dates.get(pid) or {}).get(기준일) or REF_DATE
    return REF_DATE


def age_at(birth, on):
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def months_between(start, on):
    """start(개업일)부터 on까지 꽉 찬 개월 수"""
    n = (on.year - start.year) * 12 + on.month - start.month
    if add_months(start, n) > on:
        n -= 1
    return n


def birth_range(age):
    """판정 기준일에 만 age세인 사람의 생일 범위 (가장 이른 날, 가장 늦은 날)"""
    latest = add_years(REF_DATE, -age)
    earliest = add_years(REF_DATE, -(age + 1)) + timedelta(days=1)
    return earliest, latest


def open_range(months):
    """판정 기준일에 업력 months개월인 사업자의 개업일 범위"""
    latest = add_months(REF_DATE, -months)
    earliest = add_months(REF_DATE, -(months + 1)) + timedelta(days=1)
    return earliest, latest


def merge_both_ends(a, b):
    """범위 양 끝 결과 → 둘 다 ✅ ✅ / 둘 다 ❌ ❌ / 걸치면 ❔"""
    if a == b:
        return a
    return UNK


def in_bound(x, lo, lo_kind, hi, hi_kind):
    if lo is not None:
        if lo_kind == '초과' and not x > lo:
            return False
        if lo_kind != '초과' and not x >= lo:
            return False
    if hi is not None:
        if hi_kind == '미만' and not x < hi:
            return False
        if hi_kind != '미만' and not x <= hi:
            return False
    return True


def in_date_range(d, rng):
    f, fk, t, tk = rng.get('from'), rng.get('from_경계'), rng.get('to'), rng.get('to_경계')
    if f:
        f = date.fromisoformat(f)
        if (fk == '후' and not d > f) or (fk != '후' and not d >= f):
            return False
    if t:
        t = date.fromisoformat(t)
        if (tk == '전' and not d < t) or (tk != '전' and not d <= t):
            return False
    return True


# 조건별 판정. 반환: (결과, 사유 문구 또는 None, 상세 dict)

def user_stage(u):
    s = u.get('창업단계')
    return '초기' if s in ('초기창업', '기창업', '초기창업자', '기창업자') else '예비'


def age_label(cond):
    lo, hi = cond.get('min'), cond.get('max')
    parts = []
    if lo is not None:
        parts.append(f"{lo}세 {cond.get('경계_min') or '이상'}")
    if hi is not None:
        parts.append(f"{hi}세 {cond.get('경계_max') or '이하'}")
    if cond.get('출생일_범위'):
        b = cond['출생일_범위']
        parts.append(f"{b.get('from') or ''}~{b.get('to') or ''} 출생")
    return ' '.join(parts) or '나이 조건'


def judge_age(cond, u, pid, dates):
    if cond.get('대상') not in AGE_TARGETS:
        return None
    a = u.get('만나이')
    if a is None:
        return UNK, '나이 확인 필요', {}
    on = base_date(pid, cond.get('기준일'), dates)
    lo_b, hi_b = birth_range(a)
    rs = []
    if cond.get('min') is not None or cond.get('max') is not None:
        kind = cond.get('나이_기준')
        if kind == '보험나이':
            rs.append(UNK)
        else:
            def age_fn(b):
                return on.year - b.year + 1 if kind == '연나이' else age_at(b, on)
            ends = [OK if in_bound(age_fn(b), cond.get('min'), cond.get('경계_min'), cond.get('max'), cond.get('경계_max')) else NO for b in (lo_b, hi_b)]
            rs.append(merge_both_ends(*ends))
    if cond.get('출생일_범위'):
        ends = [OK if in_date_range(b, cond['출생일_범위']) else NO for b in (lo_b, hi_b)]
        rs.append(merge_both_ends(*ends))
    if not rs:
        return UNK, '나이 확인 필요', {}
    if len(rs) == 2 and rs[0] != rs[1]:
        r = UNK
    else:
        r = rs[0]
    rng = age_label(cond)
    reason = {OK: None, NO: f'나이 {a}세 ↔ 공고 {rng}', UNK: '나이 확인 필요'}[r]
    return r, reason, {'공고': rng, '사용자': a}


def judge_years(cond, u, pid, dates):
    """업력 (초기창업자만 부름). 개월·단계·날짜가 함께 있으면 모두 맞아야 함"""
    m = u.get('업력_개월')
    if m is None:
        return UNK, '업력 확인 필요'
    if cond.get('상태') == '불명확':
        return UNK, '업력 기준 확인 필요'
    lo, lo_k, hi, hi_k = cond.get('min_개월'), cond.get('경계_min'), cond.get('max_개월'), cond.get('경계_max')
    if lo is None and hi is None and cond.get('단계'):
        lo, lo_k, hi, hi_k = {'초기': (None, None, 36, '이하'), '도약': (36, '이상', 84, '이하')}.get(cond['단계'], (None, None, None, None))
    on = base_date(pid, cond.get('기준일'), dates)
    earliest, latest = open_range(m)
    rs = []
    if lo is not None or hi is not None:
        def ok(d):
            # 'N개월 이내·이하' = 개업일 + N개월 당일까지, '미만' = 당일 제외 / 'N개월 이상' = 개업일 + N개월 당일부터
            if hi is not None:
                limit = add_months(d, hi)
                if (hi_k == '미만' and not on < limit) or (hi_k != '미만' and not on <= limit):
                    return False
            if lo is not None:
                limit = add_months(d, lo)
                if (lo_k == '초과' and not on > limit) or (lo_k != '초과' and not on >= limit):
                    return False
            return True
        rs.append(merge_both_ends(*[OK if ok(d) else NO for d in (earliest, latest)]))
    if cond.get('창업일_범위'):
        rs.append(merge_both_ends(*[OK if in_date_range(d, cond['창업일_범위']) else NO for d in (earliest, latest)]))
    if not rs:
        return UNK, '업력 기준 확인 필요'
    r = NO if NO in rs else (UNK if UNK in rs else OK)
    reason = {OK: None, NO: f'업력 {m}개월이 공고 업력 범위 밖', UNK: '업력 기준 확인 필요'}[r]
    return r, reason


def judge_registration(reg, u):
    """사업자등록 (창업단계). 예비: 필수 ❌ / 사후등록 🟡 / 불가·무관 ✅. 초기: 불가만 ❌"""
    if not reg or reg.get('상태') not in ('있음', '불명확'):
        return None
    if reg['상태'] == '불명확':
        return UNK, '사업자등록 조건 확인 필요', {}
    v = reg.get('값')
    if user_stage(u) == '예비':
        if v == '필수':
            return NO, '사업자등록 필요 (예비창업자 신청 불가)', {}
        if v == '사후등록':
            return COND, '선정 후 사업자등록 필요', {}
        return OK, None, {}
    if v == '불가':
        return NO, '예비창업자 전용 (사업자등록 있으면 신청 불가)', {}
    return OK, None, {}


def judge_years_field(yrs, u, pid, dates):
    """업력 (창업단계). 예비창업자는 0개월로 보아 업력 조건이 있으면 ❌, 초기창업자는 개월로 비교"""
    if not yrs or yrs.get('상태') not in ('있음', '불명확'):
        return None
    if user_stage(u) == '예비':
        return NO, '업력 조건 있음 (예비창업자 신청 불가)', {}
    r, why = judge_years(yrs, u, pid, dates)
    return r, why, {'사용자': u.get('업력_개월')}


def judge_applicant(cond, c, u):
    """신청자_유형: 개인사업자·법인 중 하나만 받는 전용 공고일 때만 조건"""
    if not cond or cond.get('상태') != '있음':
        return None
    vals = set(cond.get('값') or [])
    biz = vals & set(BIZ_TYPES)
    stage = user_stage(u)
    reg = (c.get('사업자등록') or {})
    if stage == '예비':
        if '예비창업자' in vals or len(biz) != 1:
            return None
        if reg.get('값') == '사후등록':
            return COND, f'선정 후 {next(iter(biz))} 설립 필요', {}
        return None
    if len(biz) == 2:
        return None
    if len(biz) == 1:
        need = next(iter(biz))
        have = u.get('사업자_형태')
        if have is None:
            return COND, f'{need}만 신청 가능', {}
        return (OK, None, {}) if have == need else (NO, f'{need}만 신청 가능 (사용자 {have})', {})
    if '예비창업자' in vals:
        return NO, '예비창업자만 신청 가능', {}
    if '대학생' in vals:
        return judge_special([{'값': '대학생'}], u)
    return UNK, '신청 대상 확인 필요', {}


def loc_match(loc, scope):
    """사용자 위치 ↔ 공고 범위 하나. True / False / None(모름)"""
    if not loc:
        return None
    if scope.get('시도') and loc.get('시도') != scope['시도']:
        return False
    if not scope.get('시군구'):
        return True
    if loc.get('시군구'):
        return loc['시군구'] == scope['시군구']
    cands = loc.get('후보_구') or []
    if cands and all(x == scope['시군구'] for x in cands):
        return True
    if cands and scope['시군구'] not in cands:
        return False
    return None


def loc_in(loc, scopes):
    rs = [loc_match(loc, s) for s in scopes]
    if True in rs:
        return True
    if None in rs:
        return None
    return False


def gu_label(scopes):
    return '·'.join(s.get('시군구') or s.get('시도') or '' for s in scopes)


SERVICE_SIDO = '서울특별시'  # 서비스 대상: 서울에서 창업하는 사람


def judge_region(cond, u):
    """지역. 판정규칙 지역 판정 표 + 판정 단계 정리(나애님) 사용자 프로필 형식
    - 공고가 서울 밖 시·도(타지역)면 누구든 ❌
    - 거주지: 서울 밖에 살면 ❌, 서울 안 다른 구면 🟡
    - 창업예정지·사업장소재지: 시도가 서울 밖이면 화면 안내 대상이라 판정하지 않음"""
    if not cond or cond.get('상태') in (None, '없음', '대안조건'):
        return None
    if cond['상태'] == '불명확' or not cond.get('범위'):
        return UNK, '지역 조건 확인 필요', {}
    scopes = cond['범위']
    label = gu_label(scopes)
    if not any(s.get('시도') == SERVICE_SIDO for s in scopes):
        return NO, f'타지역 공고 ({label})', {'공고': label}
    stage = user_stage(u)
    place_field = '사업장소재지' if stage == '초기' else '창업예정지'

    def by_type(t):
        if t in HOME_TYPES:
            fields = ['거주지']
        elif t in PLACE_TYPES:
            fields = [place_field]
        else:  # 명시없음
            fields = ['거주지', place_field]
        res = []
        for f in fields:
            loc = u.get(f)
            if f != '거주지' and loc and loc.get('시도') and loc['시도'] != SERVICE_SIDO:
                continue  # 서울 밖 창업예정지·사업장: 판정 안 함 (화면 안내)
            m = loc_in(loc, scopes)
            if m is True:
                res.append((OK, None))
            elif m is None:
                res.append((UNK, f'{f} 확인 필요'))
            elif f == '거주지':
                if loc.get('시도') != SERVICE_SIDO:
                    res.append((NO, f'거주지 {loc.get("시도")} ≠ 공고 {label}'))
                elif stage == '초기':
                    res.append((COND, f'{label} 거주 조건 확인 필요'))
                else:
                    res.append((COND, f'{label} 거주자만 신청 가능'))
            elif stage == '초기':
                gu = (loc or {}).get('시군구')
                res.append((NO, f'사업장 {gu} ≠ 공고 {label}'))
            else:
                res.append((COND, f'{label}에서 창업하면 신청 가능'))
        if not res:
            return None
        return min(res, key=lambda x: GOOD[x[0]])

    types = cond.get('유형') or ['명시없음']
    per = [x for x in (by_type(t) for t in types) if x is not None]
    if not per:
        return None
    if len(per) > 1 and cond.get('유형_결합') == '모두':
        r = min(per, key=lambda x: GOOD[x[0]])
    else:
        r = max(per, key=lambda x: GOOD[x[0]])
    return r[0], r[1], {'공고': label}


def judge_gender(cond, u):
    if not cond or cond.get('상태') != '있음' or not cond.get('값'):
        return None
    if cond.get('대상') not in (None, '대표자', '명시없음'):
        return None
    need = cond['값']
    have = u.get('성별')
    if have is None:
        return WHITE, f'{need} 대표자만 신청 가능', {}
    return (OK, None, {}) if have == need else (NO, f'{need} 대표자만 신청 가능', {})


def judge_special(items, u):
    if not items:
        return None
    rs = []
    for it in items:
        v = it.get('값') if isinstance(it, dict) else it
        if not v:
            continue
        if v == '청년':  # 만 나이로 판정 (만 39세 이하)
            a = u.get('만나이')
            rs.append((UNK, '청년 여부 확인 필요') if a is None else ((OK, None) if a <= 39 else (NO, '청년(만 39세 이하)만 신청 가능')))
            continue
        have = u.get('특수자격')
        if have is None:
            rs.append((WHITE, f'{v}만 신청 가능'))
        elif v in have:
            rs.append((OK, None))
        else:
            rs.append((NO, f'{v}만 신청 가능'))
    if not rs:
        return None
    r = min(rs, key=lambda x: GOOD[x[0]])
    return r[0], r[1], {'공고': [i.get('값') if isinstance(i, dict) else i for i in items]}


# 업종

def exception_map(entries):
    """['소매업: 단, ...'] → {'소매업': '단, ...'}"""
    out = {}
    for e in entries or []:
        k, _, rest = str(e).partition(':')
        out[k.strip()] = rest.strip()
    return out


def industry_scope(top, track, dic):
    """공고 전체 + 트랙 업종명 → 카테고리 (나애님 industry_map 만드는 규칙과 같음)
    허용은 트랙에 있으면 트랙 것, 제외·제외_목록·제외_예외는 둘을 합침"""
    t = ((top or {}).get('업종명') or {})
    k = ((track or {}).get('업종명') or {})
    allow_kw = list(k.get('허용') or []) or list(t.get('허용') or [])
    excl_kw = []
    for src in (t, k):
        for kw in (src.get('제외') or []) + (src.get('제외_목록') or []):
            if kw not in excl_kw:
                excl_kw.append(kw)
    exc = {**exception_map(t.get('제외_예외')), **exception_map(k.get('제외_예외'))}

    allow, unknown_allow = set(), []
    for kw in allow_kw:
        cats = (dic.get(kw.strip()) or {}).get('허용') or []
        allow |= set(cats)
        if not cats:
            unknown_allow.append(kw)
    excl, excexc = set(), set()
    excl_detail = []  # (키워드, 카테고리들, 예외 문구 또는 None). 사전에 없는 키워드도 원문 확인용으로 둠
    for kw in excl_kw:
        cats = (dic.get(kw.strip()) or {}).get('제외') or []
        e = exc.get(kw.strip())
        (excexc if e is not None else excl).update(cats)
        excl_detail.append((kw, cats, e))
    excexc -= excl
    status = ((track or {}).get('상태') if track and track.get('업종명') else None) or (top or {}).get('상태')
    return {
        '허용': '전체' if not allow_kw else sorted(allow),
        '허용_키워드': allow_kw, '허용_미매칭': unknown_allow,
        '제외': sorted(excl), '제외_예외': sorted(excexc), '제외_상세': excl_detail,
        '상태': status,
    }


def load_industry_map(path):
    out = {}
    for r in read_csv(path):
        split = lambda s: sorted(x for x in (s or '').split('|') if x)
        out[(r['pblancId'], r['트랙'])] = {
            '허용': '전체' if r['허용'] == '전체' else split(r['허용']),
            '제외': split(r['제외']), '제외_예외': split(r['제외_예외'])}
    return out


def apply_map(sc, row):
    """industry_map.csv 줄이 있으면 카테고리를 그 줄로 바꾼다 (키워드 상세는 JSON 것 유지)"""
    if not row:
        return sc
    return {**sc, **row}


def has_any(text, words):
    return any(w in (text or '') for w in words)


def exception_decision(kw, text):
    rule = EXCEPTION_RULES.get(kw.strip())
    if not rule:
        return None
    if has_any(text, rule['in']):
        return 'in'
    if has_any(text, rule['out']):
        return 'out'
    return None


def keyword_hit(kw, kcats, cats, text):
    """제외 키워드 하나에 사용자가 걸리는지: 'hit' / 'unsure' / None
    - 카테고리 통째 제외: 사용자 카테고리('기타' 빼고)가 겹치면 hit
    - 카테고리 안에서 갈리는 부분 제외(주점·유흥 등)와 '기타' 사용자: 업종 원문으로 확인"""
    if any(c != '기타' and c in kcats for c in cats):
        return 'hit'
    for words, sub in RAW_TAGS:
        if sub in kw and has_any(text, words):
            return 'hit'
    for sub, cat, in_words, unsure_words in PARTIAL_EXCL:
        if sub in kw and (cat is None or cat in cats):
            if has_any(text, in_words):
                return 'hit'
            if has_any(text, unsure_words):
                return 'unsure'
    return None


def judge_industry(sc, u):
    """업종. 반환 (결과, 사유, 상세{industry_reason, industry_hit})"""
    no_cond = sc['허용'] == '전체' and not sc['제외_상세']
    if no_cond and sc['상태'] != '불명확':
        return None
    stage = user_stage(u)
    cats = u.get('업종') or []
    text = u.get('industry') or ''
    miss = COND if stage == '예비' else NO
    allow = sc['허용']
    allow_names = '·'.join(sc['허용_키워드'][:3]) + (f" 외 {len(sc['허용_키워드']) - 3}개" if len(sc['허용_키워드']) > 3 else '')

    def fail(kind, hit_kw=None, hit_cat=None):
        if kind == '제외':
            name = hit_kw or hit_cat
            why = f'{name} 업종 제외' if stage == '초기' else f'{name} 외 업종으로 창업하면 신청 가능'
            return miss, why, {'industry_reason': '제외', 'industry_hit': [hit_kw] if hit_kw else [hit_cat]}
        why = f'{allow_names} 업종만 신청 가능' if stage == '초기' else f'{allow_names} 분야로 창업하면 신청 가능'
        return miss, why, {'industry_reason': '허용불일치'}

    def unknown(why):
        return UNK, why, {'industry_reason': '확인필요'}

    if sc['상태'] == '불명확' and allow == '전체' and not sc['제외_상세']:
        return unknown('업종 조건 확인 필요')
    if not cats:
        return unknown('업종 확인 필요')

    # 키워드마다 제외를 보고, '기타'·부분 제외·예외는 업종 원문으로 확인
    excluded, unsure = None, None
    for kw, kcats, exc in sc['제외_상세']:
        h = keyword_hit(kw, kcats, cats, text)
        if h is None:
            continue
        if h == 'unsure':
            unsure = unsure or kw
            continue
        if exc is None:
            excluded = excluded or kw
            continue
        dec = exception_decision(kw, text)  # 예외("단, ~은 가능")에 들어가는지
        if dec == 'out':
            excluded = excluded or kw
        elif dec is None:
            unsure = unsure or kw
    if excluded:
        return fail('제외', hit_kw=excluded)
    tag_subs = [sub for words, sub in RAW_TAGS if has_any(text, words)]
    if allow == '전체':
        ok = True
    else:
        ok = (any(c != '기타' and c in allow for c in cats) or any(sub in kw for sub in tag_subs for kw in sc['허용_키워드']))
    if not ok:
        if '기타' in cats and not tag_subs:
            return unknown('업종 확인 필요')
        if sc['허용_미매칭']:
            return unknown('업종 조건 확인 필요')
        return fail('허용')
    if unsure:
        return unknown(f'{unsure} 해당 여부 확인 필요')
    return OK, None, {}


# 대안조건

def option_text(opt):
    parts = []
    for k, v in opt.items():
        if k == '업력' and isinstance(v, dict):
            if v.get('max_개월'):
                parts.append(f"업력 {v['max_개월']}개월 {v.get('경계_max') or '이하'}")
            elif v.get('min_개월'):
                parts.append(f"업력 {v['min_개월']}개월 {v.get('경계_min') or '이상'}")
            else:
                parts.append('창업기업 업력 기준 안')
        elif k == '나이' and isinstance(v, dict):
            parts.append('나이 ' + age_label(v))
        elif k == '특수자격':
            items = v if isinstance(v, list) else [v]
            parts.append('·'.join(str(i.get('값') if isinstance(i, dict) else i) for i in items))
        elif k == '보유요건':
            items = v if isinstance(v, list) else [v]
            parts.append('·'.join((i.get('내용') or i.get('종류') or '') for i in items if isinstance(i, dict)))
        elif isinstance(v, dict):
            parts.append(v.get('내용') or v.get('설명') or k)
        else:
            parts.append(k)
    return ' + '.join(p for p in parts if p)


def judge_option(opt, c, u, pid, dates, dic):
    """선택지 하나 = 칸들의 AND. 판정 안 하는 칸(보유요건·기타조건 등)은 ❔"""
    rs = []
    for k, v in opt.items():
        r = None
        if k == '업력':
            x = judge_years_field(v, u, pid, dates)
            r = (OK, None) if x is None else x[:2]
        elif k == '나이':
            x = judge_age(v, u, pid, dates)
            r = (OK, None) if x is None else x[:2]
        elif k == '특수자격':
            x = judge_special(v if isinstance(v, list) else [v], u)
            r = (OK, None) if x is None else x[:2]
        elif k == '성별':
            x = judge_gender(v, u)
            r = (OK, None) if x is None else x[:2]
        elif k == '지역':
            x = judge_region(v, u)
            r = (OK, None) if x is None else x[:2]
        elif k == '사업자등록':
            x = judge_registration(v, u)
            r = (OK, None) if x is None else x[:2]
        elif k == '신청자_유형':
            x = judge_applicant(v, c, u)
            r = (OK, None) if x is None else x[:2]
        elif k == '업종':
            x = judge_industry(industry_scope(v, None, dic), u)
            r = (OK, None) if x is None else x[:2]
        elif k == '기업규모':
            r = (OK, None)
        else:
            r = (UNK, None)
        rs.append(r)
    if not rs:
        return OK, None
    return min(rs, key=lambda x: GOOD[x[0]])


def judge_alternatives(alts, c, u, pid, dates, dic):
    """대안조건마다 선택지 중 가장 좋은 결과. alt_left = ❌ 아닌 선택지 번호(JSON 순서, 0부터)"""
    out = []
    for a in alts:
        opts = [o for o in a.get('선택지') or [] if o]
        if not opts:
            continue
        if not any(set(o) & JUDGED_KEYS for o in opts):
            continue  # 판정하는 칸이 하나도 없는 대안조건은 판정 안 함(통과)
        res = [judge_option(o, c, u, pid, dates, dic) for o in opts]
        best_i = max(range(len(opts)), key=lambda i: GOOD[res[i][0]])
        best = res[best_i][0]
        left = [i for i, r in enumerate(res) if r[0] != NO]
        if best == OK:
            out.append((OK, None, {'설명': a.get('설명')}))
            continue
        if best == NO:
            why = f"{a.get('설명') or '대안조건'} 불충족"
        else:
            why = f'{option_text(opts[best_i])}이면 신청 가능'
        out.append((best, why, {'설명': a.get('설명'), 'alt_left': left, 'alt_left_text': [option_text(opts[i]) for i in left]}))
    return out


# 공고 하나 × 사용자

def scoped(top, track):
    """공고 전체 조건 + 트랙 조건. 같은 칸은 트랙이 덮어쓰고, 목록 칸은 합침"""
    c = {k: v for k, v in top.items() if k not in ('트랙',)}
    if track:
        for k, v in (track.get('조건') or {}).items():
            if k in LIST_KEYS:
                c[k] = list(c.get(k) or []) + list(v or [])
            else:
                c[k] = v
    return c


def verify(c, pid, ev, where):
    """근거를 원문에서 못 찾은 조건은 미기재(없음)로 바꾼다"""
    c = dict(c)
    for k in ('나이', '성별', '지역', '업력', '사업자등록', '신청자_유형'):
        if isinstance(c.get(k), dict) and c[k].get('상태') in ('있음', '불명확'):
            if ev.check(pid, f'{where}.{k}', c[k]) is None:
                c[k] = {'상태': '없음'}
    if c.get('특수자격'):
        c['특수자격'] = [i for i in c['특수자격'] if ev.check(pid, f'{where}.특수자격', i) is not None]
    alts = []
    for a in c.get('대안조건') or []:
        opts = []
        for o in a.get('선택지') or []:
            o2 = {}
            for k, v in o.items():
                if isinstance(v, dict) and ev.check(pid, f'{where}.대안조건.{k}', v) is None:
                    continue
                o2[k] = v
            if o2:
                opts.append(o2)
        if opts:
            alts.append({**a, '선택지': opts})
    c['대안조건'] = alts
    return c


def signal_of(results):
    rs = [r for r, _, _ in results.values()]
    if NO in rs:
        return '🔴'
    if WHITE in rs or rs.count(UNK) >= 2:
        return '⚪'
    if COND in rs or UNK in rs:
        return '🟡'
    return '🟢'


def judge_scope(top, track, u, pid, dates, ev, dic):
    c = verify(scoped(top, track), pid, ev, track['이름'] if track else '전체')
    res = {}

    def put(name, x):
        if x is not None:
            res[name] = x

    put('사업자등록', judge_registration(c.get('사업자등록'), u))
    put('업력', judge_years_field(c.get('업력'), u, pid, dates))
    put('신청자_유형', judge_applicant(c.get('신청자_유형'), c, u))
    put('지역', judge_region(c.get('지역'), u))
    age = c.get('나이') or {}
    if age.get('상태') in ('있음', '불명확'):
        put('나이', (UNK, '나이 조건 확인 필요', {}) if age['상태'] == '불명확'
            else judge_age(age, u, pid, dates))
    put('성별', judge_gender(c.get('성별'), u))
    sc = industry_scope(top.get('업종'), (track or {}).get('조건', {}).get('업종'), dic)
    if IND_MAP is not None:
        sc = apply_map(sc, IND_MAP.get((pid, track['이름'] if track else '')))
    put('업종', judge_industry(sc, u))
    put('특수자격', judge_special(c.get('특수자격'), u))
    for i, x in enumerate(judge_alternatives(c.get('대안조건') or [], c, u, pid, dates, dic)):
        res['대안조건' if i == 0 else f'대안조건{i + 1}'] = x
    if not res:  # 판정 조건을 하나도 못 뽑음
        return '⚪', {'자격조건': (UNK, '자격 조건 미기재', {})}, c
    return signal_of(res), res, c


def judge_pair(cond, u, pid, dates, ev, dic):
    tracks = cond.get('트랙') or []
    cands = []
    for t in (tracks or [None]):
        sig, res, c = judge_scope(cond, t, u, pid, dates, ev, dic)
        cands.append((sig, res, c, t['이름'] if t else ''))
    best = max(cands, key=lambda x: SIGNAL_GOOD[x[0]])  # 같으면 앞 트랙
    sig, res, c, name = best
    return sig, res, c, name, cands


def checklist(c):
    items = []
    for k in CHECKLIST_KEYS:
        v = c.get(k)
        if isinstance(v, list):
            items += [f"{k}: {i.get('내용') or i.get('종류') or i.get('유형') or ''}" for i in v if isinstance(i, dict)]
        elif isinstance(v, dict) and v.get('상태') in ('있음', '불명확'):
            items.append(f'{k}: {v.get("근거") or v.get("구분") or ""}')
    for a in c.get('대안조건') or []:  # 판정하는 칸이 없는 대안조건
        if not any(set(o) & JUDGED_KEYS for o in a.get('선택지') or []):
            items.append(f"대안조건: {a.get('설명') or ''}")
    return items


def reason_text(sig, res):
    """신호등 사유: 🔴은 ❌ 조건, 🟡·⚪은 ✅ 아닌 조건의 [조건] 문구"""
    keys = sorted(res, key=lambda k: ORDER.index(re.sub(r'\d+$', '', k)) if re.sub(r'\d+$', '', k) in ORDER else 99)
    if sig == '🔴':
        whys = [res[k][1] for k in keys if res[k][0] == NO]
    else:
        whys = [res[k][1] for k in keys if res[k][0] != OK]
    return ' / '.join(w for w in whys if w)


# 채점

def emoji(label):
    e = (label or '').strip().replace('️', '')[:1]
    return e if e in LABELS else ''


def metrics(pairs):
    green = [g for g, p in pairs if p == '🟢']
    per_class = {}
    for c in LABELS:
        tp = sum(g == c and p == c for g, p in pairs)
        pred = sum(p == c for _, p in pairs)
        gold = sum(g == c for g, _ in pairs)
        prec = tp / pred if pred else 0
        rec = tp / gold if gold else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        per_class[c] = {'P': round(prec, 3), 'R': round(rec, 3), 'F1': round(f1, 3)}
    return {
        '쌍 수': len(pairs),
        'Accuracy': round(sum(g == p for g, p in pairs) / len(pairs), 3),
        'False green': round(sum(g != '🟢' for g in green) / len(green), 3) if green else 0,
        '🟢 예측 수': len(green),
        'Macro-F1': round(sum(v['F1'] for v in per_class.values()) / 4, 3),
        '클래스별': per_class,
        '혼동행렬(정답→예측)': {g: dict(Counter(p for gg, p in pairs if gg == g)) for g in LABELS},
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap = argparse.ArgumentParser()
    ap.add_argument('--conds', required=True, help='공고별 조건 JSON 폴더 (PBLN_*.json)')
    ap.add_argument('--out', required=True, help='결과 파일 앞부분 (예: proposal/results/judge_p1_gold)')
    ap.add_argument('--users', default=os.path.join(root, 'goldset', 'users_v2.csv'))
    ap.add_argument('--gold', default=os.path.join(root, 'goldset', 'judge_gold_v2.csv'))
    ap.add_argument('--industry-dict', default=os.path.join(here, '업종_사전.csv'))
    ap.add_argument('--dates', default=os.path.join(here, 'ann_dates.csv'))
    ap.add_argument('--texts', default=os.path.join(root, 'texts_gold30'), help='근거 검증용 원문 폴더. 없으면 검증 안 함')
    ap.add_argument('--industry-map', default=None, help='주면 업종 카테고리를 나애님 industry_map.csv 줄로 판정 (기본: 업종_사전으로 JSON에서 만듦)')
    a = ap.parse_args()
    global IND_MAP
    IND_MAP = load_industry_map(a.industry_map) if a.industry_map else None

    users = load_users(a.users)
    conds = load_conds(a.conds)
    dates = load_dates(a.dates)
    dic = load_industry_dict(a.industry_dict)
    ev = Evidence(a.texts if os.path.isdir(a.texts) else None)
    gold = read_csv(a.gold)

    rows, detail = [], []
    for g in gold:
        pid, uid = g['공고ID'], g['사용자']
        if pid not in conds:
            sig, res, c, track, cands = '⚪', {'자격조건': (UNK, '조건 JSON 없음', {})}, {}, '', []
        else:
            sig, res, c, track, cands = judge_pair(conds[pid], users[uid], pid, dates, ev, dic, )
        reason = reason_text(sig, res)
        ind = (res.get('업종') or (None, None, {}))[2]
        alt = (res.get('대안조건') or (None, None, {}))[2]
        rows.append({
            '사용자': uid, '공고ID': pid, '예측': LABELS[sig], '정답': g['정답'],
            '일치': 'O' if emoji(g['정답']) == sig else 'X',
            '사유': reason, '정답 사유': g.get('사유', ''), '트랙': track,
            '조건별': ' '.join(f'{k}{v[0]}' for k, v in res.items()),
        })
        detail.append({
            'user_id': uid, 'pblancId': pid,
            'signal': sig,
            'stage': '초기창업' if user_stage(users[uid]) == '초기' else '예비창업',
            'results': {k: (UNK if v[0] == WHITE else v[0]) for k, v in res.items() if k != '자격조건'},
            'track': track or None,
            **({'industry_reason': ind['industry_reason']} if ind.get('industry_reason') else {}),
            **({'industry_hit': ind['industry_hit']} if ind.get('industry_hit') else {}),
            **({'alt_left': alt['alt_left']} if alt.get('alt_left') is not None else {}),
            # 아래는 확인용 (조건 문구 함수에는 안 넘겨도 됨)
            '사유': reason,
            '조건별_문구': {k: v[1] for k, v in res.items() if v[1]},
            '체크리스트': checklist(c),
            '트랙별': [{'트랙': n, 'signal': s, 'results': {k: v[0] for k, v in r.items()}}
                    for s, r, _, n in cands],
        })

    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out + '_pred.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(a.out + '_detail.json', 'w', encoding='utf-8') as f:
        json.dump(detail, f, ensure_ascii=False, indent=1)

    pairs = [(emoji(r['정답']), emoji(r['예측'])) for r in rows]
    m = {'설정': {'conds': a.conds, '근거 검증': bool(ev.folder), '판정 기준일': str(REF_DATE)}, '전체': metrics(pairs),
         '근거 못 찾아 뺀 조건': [{'공고ID': p, '위치': w, '근거': e} for p, w, e in sorted(set(ev.dropped))]}
    with open(a.out + '_metrics.json', 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=1)

    t = m['전체']
    print(f"{a.conds}  ({len(rows)}쌍)")
    print(f"  Accuracy {t['Accuracy']}  False green {t['False green']} ({t['🟢 예측 수']}개 중)  Macro-F1 {t['Macro-F1']}")
    print(f"  근거 못 찾아 뺀 조건 {len(m['근거 못 찾아 뺀 조건'])}개")


if __name__ == '__main__':
    main()
