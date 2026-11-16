"""
검색 부품 모음. 검색 대상은 docs_snap1016.jsonl (공고 342건)

기본 검색 순서 (search_service.py)
1. clean_passages : 사업개요 + 원문 500자 문단, 잡음 문단 제외
2. Hybrid         : 키워드(V0) + 의미(V1) 순위를 합침
3. RegionFilter   : 타지역·통합공고 제외, 다른 구 공고는 뒤로
4. NeedBoost      : 원하는 지원은 올리고 특수 대상 공고는 내림
"""
import csv, json, re
from pathlib import Path
import numpy as np

RAG      = Path(__file__).resolve().parent.parent
DATA     = RAG / "02_검색대상_시험지" / "docs_snap1016.jsonl"
CATEGORY = RAG / "02_검색대상_시험지" / "category_map.csv"
TEXTS    = RAG / "01_원본" / "texts_v8_20261024" / "texts"
CACHE    = RAG / "04_실험_시험+채점결과" / "cache"

DOCS = [json.loads(l) for l in open(DATA, encoding="utf-8")]
IDS = [d["pblancId"] for d in DOCS]
DOC_BY_ID = dict(zip(IDS, DOCS))

# 통합공고: 여러 사업 안내용이라 직접 신청 불가 (11/10 회의에서 제외 결정)
GUIDE_IDS = {"PBLN_000000000116904",   # 중앙부처 및 지자체 창업지원사업 통합 공고
             "PBLN_000000000117016",   # 소상공인 지원사업 통합 공고
             "PBLN_000000000118204",   # 여성기업 육성사업 공고
             "PBLN_000000000116741"}   # 중소기업 수출지원사업 통합 공고

# 원문이 없는 공고: 조건을 못 뽑아서 판정 불가 (11/16 제외 결정)
NO_TEXT_IDS = {"PBLN_000000000119754",   # 팁스(TIPS) 창업기업 지원계획
               "PBLN_000000000121498",   # 농업용 면세유 유가연동보조금
               "PBLN_000000000123334",   # 소상공인 무료 법률·세무·노무 간편상담
               "PBLN_000000000124676",   # 소상공인 안전검사 지원 (생활용품·어린이제품)
               "PBLN_000000000125810",   # 강남구 청년일자리도약장려금
               "PBLN_000000000126188",   # 위치정보 맞춤형 컨설팅
               "PBLN_000000000126865"}   # 서리풀 소상공인 창업 클리닉

# 사용자가 신청하는 공고가 아님 (예은님 조건 추출에서도 뺌, 11/16)
NOT_APPLY_IDS = {"PBLN_000000000092578",   # 체납액 징수특례 제도 안내 (모집 공고 아님)
                 "PBLN_000000000116975",   # 넷제로 챌린지X 통합 공고 (자격이 개별 공고에)
                 "PBLN_000000000122497",   # SW개발자 채용기업 모집 (채용공고 양식뿐)
                 "PBLN_000000000127096"}   # 초격차 정부 첫 실증·구매 주관기관 모집 (신청 대상이 주관기관)

# 폐업(예정)자 전용: 서비스 대상 아님, 판정규칙 1-6 (11/16)
CLOSING_ONLY_IDS = {"PBLN_000000000117676",   # 희망리턴패키지 원스톱폐업지원
                    "PBLN_000000000117673",   # 희망리턴패키지 특화취업지원
                    "PBLN_000000000119017"}   # 새 길 여는 폐업지원

# 검색에서 빼고 채점에서 0점 처리하는 공고 전체
EXCLUDE_IDS = GUIDE_IDS | NO_TEXT_IDS | NOT_APPLY_IDS | CLOSING_ONLY_IDS

# 지방 센터 운영: 자격은 전국이라 안 빼지만 프로그램이 그 지역에서 열림 → 6위 아래로 (11/16)
LOCAL_RUN_IDS = {"PBLN_000000000117984",   # 제주센터 창업-BuS
                 "PBLN_000000000118729",   # 경북센터 창업-BuS
                 "PBLN_000000000119817",   # 광주센터 창업BuS
                 "PBLN_000000000119999",   # 인천센터 창업-BuS
                 "PBLN_000000000120946",   # 전남센터 창업 BuS
                 "PBLN_000000000126928"}   # 오픈이노베이션 (충북센터)


# 1. 문단 만들기 ------------------------------------------------------------
def summary_passages():
    """공고 1건 = 공고명 + 사업개요 1조각"""
    return [f'{d["pblancNm"]}\n{d["summary"]}' for d in DOCS], list(IDS)

def split_text(text, size=500):
    """줄 단위로 모아 size 글자 정도씩 자름. 30자 미만 조각은 버림"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    chunks, cur = [], ""
    for line in lines:
        while len(line) > size:
            if cur: chunks.append(cur); cur = ""
            chunks.append(line[:size]); line = line[size:]
        if len(cur) + len(line) + 1 > size and cur:
            chunks.append(cur); cur = ""
        cur = f"{cur}\n{line}" if cur else line
    if cur: chunks.append(cur)
    return [c for c in chunks if len(c) >= 30]

def original_passages(size=500):
    """사업개요 조각 + 원문 문단. 원문 문단 앞에는 [공고명]을 붙임"""
    texts, owners = summary_passages()
    for d in DOCS:
        f = TEXTS / f'{d["pblancId"]}.txt'
        if not d["has_text"] or not f.exists():
            continue
        for c in split_text(f.read_text(encoding="utf-8"), size):
            texts.append(f'[{d["pblancNm"]}]\n{c}')
            owners.append(d["pblancId"])
    return texts, owners

# 업종표, 신청서 양식, 연락처 목록은 질문과 엉뚱하게 맞아서 뺌
_CODE  = re.compile(r'(?<![\d.,~\-])\d{2,5}(?![\d.,%년월일개원명세시분])')
_PHONE = re.compile(r'\d{2,4}\)?[-‐ ]\d{3,4}[-‐]\d{4}')
_IND   = re.compile(r'표준산업분류|업종코드|제외 ?업종|제한 ?업종|보증제한|지원제외업종|융자제외')
_ELIG  = re.compile(r'신청 ?자격|지원 ?대상|모집 ?대상|자격 ?요건|신청 ?대상|참여 ?대상')
_FORM  = re.compile(r'성 ?명|생년월일|연락처|서명|\(인\)|동의합니다|휴대폰|이메일|주소')
_SIGN  = re.compile(r'동의|서명|\(인\)|신청서|서식|양식')

def noise_type(passage):
    b = passage.split("\n", 1)[1] if passage.startswith("[") else passage
    code = len(_CODE.findall(b))
    if code >= 8 and (_IND.search(b) or code >= 15):
        return "업종표"
    if _ELIG.search(b):
        return None                     # 자격 설명이 있으면 남김
    if b.count("□") >= 6 or (len(_FORM.findall(b)) >= 4 and _SIGN.search(b)):
        return "서식"
    if len(_PHONE.findall(b)) >= 3:
        return "연락처"
    return None

def clean_passages(size=500):
    """잡음 문단을 뺀 문단. rows는 원래 위치(임베딩 재사용용)"""
    texts, owners = original_passages(size)
    rows = [i for i, t in enumerate(texts) if i < len(DOCS) or noise_type(t) is None]
    return [texts[i] for i in rows], [owners[i] for i in rows], rows

def _to_doc_ranking(scores, owners):
    """문단 점수를 공고 순위로. 공고 점수 = 그 공고의 가장 높은 문단 점수"""
    seen, ranking = set(), []
    for i in np.argsort(-np.asarray(scores)):
        pid = owners[i]
        if pid not in seen:
            seen.add(pid); ranking.append(pid)
    return ranking


# 2. 키워드 · 의미 · 하이브리드 -----------------------------------------------
_kiwi = None
def tokenize(text):
    """명사, 동사·형용사 어간, 영어, 숫자만"""
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return [t.form for t in _kiwi.tokenize(text)
            if t.tag.startswith(("NN", "VV", "VA", "XR", "SL", "SN"))]

class V0:
    """키워드 검색 (BM25)"""
    def __init__(self, passages):
        from rank_bm25 import BM25Okapi
        self.texts, self.owners = passages
        self.bm = BM25Okapi([tokenize(t) for t in self.texts])
    def search(self, query, k=10):
        return _to_doc_ranking(self.bm.get_scores(tokenize(query)), self.owners)[:k]

_model = None
def bge_m3():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("BAAI/bge-m3")
    return _model

class V1:
    """의미 검색 (bge-m3). 임베딩은 cache에 있는 것을 씀 (build_emb.py로 만듦)"""
    def __init__(self, passages, cache_name="emb_v2b_v8_passage500.npy", rows=None):
        self.texts, self.owners = passages
        self.m = bge_m3()
        CACHE.mkdir(parents=True, exist_ok=True)
        path = CACHE / cache_name
        if path.exists():
            self.E = np.load(path)
        else:
            self.E = self.m.encode(self.texts, normalize_embeddings=True, batch_size=16, show_progress_bar=True)
            np.save(path, self.E)
        if rows is not None:
            self.E = self.E[rows]
        assert len(self.E) == len(self.texts), f"임베딩 수와 문단 수가 다름: cache/{cache_name} 확인"
        self._last = (None, None)
    def _sims(self, query):
        if self._last[0] != query:
            q = self.m.encode([query], normalize_embeddings=True)[0]
            self._last = (query, self.E @ q)
        return self._last[1]
    def search(self, query, k=10):
        return _to_doc_ranking(self._sims(query), self.owners)[:k]
    def best_passages(self, query):
        """공고별로 질문과 가장 가까운 문단 {공고ID: 문단}"""
        best = {}
        for i in np.argsort(-self._sims(query)):
            best.setdefault(self.owners[i], self.texts[i])
        return best

class Hybrid:
    """RRF: 점수 = 1/(60 + 키워드 순위) + 1/(60 + 의미 순위)"""
    def __init__(self, a, b, K=60):
        self.a, self.b, self.K = a, b, K
    def scores(self, query):
        score = {}
        for ranked in (self.a.search(query, len(IDS)), self.b.search(query, len(IDS))):
            for r, pid in enumerate(ranked, 1):
                score[pid] = score.get(pid, 0) + 1 / (self.K + r)
        return score
    def search(self, query, k=10):
        score = self.scores(query)
        return sorted(score, key=score.get, reverse=True)[:k]


# 3. 지역 거르기 -------------------------------------------------------------
def region_ok(pid, user_gu, gu_strict=True):
    """타지역은 안 됨. gu_strict면 다른 구 전용 공고도 안 됨 (구를 모르면 통과)"""
    d = DOC_BY_ID[pid]
    if d["region"] == "타지역":
        return False
    if gu_strict and d["seoul_gu"] and user_gu and user_gu not in d["seoul_gu"]:
        return False
    return True

def own_first(ranked, user_gu, n, gu=True, local=False):
    """상위 n칸은 내 구·전국·서울 공통 공고로 채움. local이면 지방 운영 공고도 뒤로"""
    top = [p for p in ranked if (not gu or region_ok(p, user_gu, gu_strict=True))
           and not (local and p in LOCAL_RUN_IDS)][:n]
    return top + [p for p in ranked if p not in top]

class RegionFilter:
    """
    demote_other_gu=5 : 다른 구 공고를 6위 아래로 (빼지는 않음)
    stage_aware       : 개업한 사용자는 다른 구 공고를 뺌 (구 이동은 예비창업자만)
    drop_guide        : 통합공고·원문 없는 공고·신청 대상 아닌 공고·폐업 전용(EXCLUDE_IDS) 뺌
    demote_local      : 지방 운영 공고(LOCAL_RUN_IDS)를 6위 아래로
    """
    def __init__(self, base, gu_strict=True, demote_other_gu=0, stage_aware=False, drop_guide=False, demote_local=False):
        self.base = base
        self.gu_strict = gu_strict and not demote_other_gu
        self.demote = demote_other_gu
        self.stage_aware = stage_aware
        self.drop_guide = drop_guide
        self.demote_local = demote_local
    def demote_for(self, stage):
        return 0 if (self.stage_aware and stage == "개업") else self.demote
    def front(self, ranked, user_gu, stage):
        """다른 구·지방 운영 공고를 상위 5칸 밖으로"""
        demote = self.demote_for(stage)
        if demote or self.demote_local:
            ranked = own_first(ranked, user_gu, demote or 5, gu=bool(demote), local=self.demote_local)
        return ranked
    def search(self, query, k=10, user_gu="", stage=""):
        demote = self.demote_for(stage)
        strict = self.gu_strict or (self.demote and not demote)
        ranked = [p for p in self.base.search(query, len(IDS)) if region_ok(p, user_gu, strict)]
        if self.drop_guide:
            ranked = [p for p in ranked if p not in EXCLUDE_IDS]
        return self.front(ranked, user_gu, stage)[:k]


# 4. 순서 조정 ---------------------------------------------------------------
# 사용자가 말하지 않은 특수 대상 공고. 빼지 않고 순위만 내림
TECH_USER = re.compile(r"앱|AI|IT|소프트웨어|플랫폼|기술")
LOCAL_BIZ = re.compile(r"카페|음식|식당|치킨|분식|떡볶이|디저트|베이커리|쿠키|잼|꽃|네일|미용|소품|핸드메이드|한복|서점|반찬|액세서리|반려")
FIELD_ONLY = {"핀테크": r"핀테크|금융서비스", "물산업": r"물산업", "기후": r"기후|탄소|넷제로", "딥테크": r"딥테크|출연\(연\)",
              "위치정보": r"위치정보", "ICT": r"ICT"}

def special_target(pid, question, stage="", industry="", age=""):
    """특수 대상이면 이유, 아니면 None. 공고명 + 사업개요 첫 '☞' 줄(지원 대상)을 봄"""
    d = DOC_BY_ID[pid]
    parts = d["summary"].split("☞")
    t = d["pblancNm"] + " " + (parts[1] if len(parts) > 1 else "")
    user = industry + " " + question
    if "장애인" in t and "장애" not in question:
        return "장애인"
    if "주관기관" in t:
        return "주관기관"
    if stage == "예비" and re.search(r"폐업|위기 소상공인|재기|희망리턴", t) and "예비창업" not in t:
        return "폐업·위기"
    if re.search(r"기술창업\s?기반", t) and LOCAL_BIZ.search(user):
        return "기술창업"
    if not TECH_USER.search(user):
        for k, pat in FIELD_ONLY.items():
            if re.search(pat, t) and not re.search(pat, user):
                return k
    if "중장년" in t and age and int(age) < 40:
        return "중장년"
    return None

def industry_mismatch(pid, user_cats):
    """공고 업종(industry_map.csv)과 사용자 업종 카테고리가 안 맞으면 True
    허용이 '전체'가 아닌데 하나도 안 겹치거나, 제외에 걸리면 안 맞음. 업종 모름·기타면 판단 안 함"""
    if not user_cats or user_cats <= {"기타"} or pid not in INDUSTRY:
        return False
    allow, deny = INDUSTRY[pid]
    return (allow != {"전체"} and not (allow & user_cats)) or bool(deny & user_cats)

def _load_industry():
    if not INDUSTRY_MAP.exists():
        return {}
    with open(INDUSTRY_MAP, encoding="utf-8-sig") as f:      # 트랙 빈칸 = 공고 전체 줄만 씀
        return {r["pblancId"]: (set(r["허용"].split("|")), set(filter(None, r["제외"].split("|"))))
                for r in csv.DictReader(f) if not r.get("트랙")}

INDUSTRY_MAP = RAG / "02_검색대상_시험지" / "industry_map.csv"
INDUSTRY = _load_industry()

def _load_age():
    path = RAG / "02_검색대상_시험지" / "age_map.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig") as f:
        return {r["pblancId"]: (float(r["min"]) if r["min"] else None, float(r["max"]) if r["max"] else None)
                for r in csv.DictReader(f)}

AGE = _load_age()

def age_mismatch(pid, age):
    """공고 나이 조건(age_map.csv, 대표자·본인 기준)과 사용자 나이가 안 맞으면 True. 나이 모르면 판단 안 함"""
    if not age or pid not in AGE:
        return False
    lo, hi = AGE[pid]
    a = float(age)
    return (lo is not None and a < lo) or (hi is not None and a > hi)

# 원하는 지원별로 질문 뒤에 붙일 공고 쪽 단어 (make_category.py KEYWORDS에서 고름, 질문지 보고 고른 것 아님)
NEED_HINT = {
    "자금": "자금 융자 보증 정책자금 지원금 사업화자금",
    "교육·컨설팅": "교육 컨설팅 멘토링 상담 코칭",
    "공간·시설": "공간 입주 시설 장비 점포 매장",
    "홍보·판매": "판로 홍보 마케팅 판매 라이브커머스 입점",
    "인력": "채용 인건비 고용지원 일자리",
    "기술개발": "R&D 기술개발 시제품 특허",
    "해외진출": "해외 수출 글로벌",
    "제도·인증": "인증 확인서",
}
# 넓은 말만 (카테고리 이름 수준). 융자·멘토링처럼 한 방식으로 좁히는 말은 뺌
NEED_HINT_SHORT = {
    "자금": "자금 지원금",
    "교육·컨설팅": "교육 컨설팅",
    "공간·시설": "공간 시설",
    "홍보·판매": "판로 홍보 판매",
    "인력": "채용 인건비",
    "기술개발": "기술개발 R&D",
    "해외진출": "해외 수출",
    "제도·인증": "인증",
}

class NeedBoost:
    """
    상위 n개 안에서만 순서를 바꿈 (Recall@n은 그대로)
    - 원하는 지원(need)과 공고 카테고리가 같으면 점수 + bonus
    - special_penalty가 있으면 특수 대상 공고 점수 - penalty
    - industry_penalty가 있으면 업종 안 맞는 공고 점수 - penalty (industry_cat: "음식·카페|도소매·판매")
    - age_rule이면 나이 조건 안 맞는 공고도 특수 대상처럼 내림 (특수 대상과 겹치면 한 번만)
    """
    def __init__(self, first, scorer, n=20, bonus=0.01, special_penalty=0.0, industry_penalty=0.0, age_rule=False,
                 need_hint=False):
        self.first, self.scorer, self.n, self.bonus = first, scorer, n, bonus
        self.penalty = special_penalty
        self.ind_penalty = industry_penalty
        self.age_rule = age_rule
        # 원하는 지원 단어를 질문 뒤에 붙여서 검색. True면 NEED_HINT, dict면 그 단어
        self.need_hint = NEED_HINT if need_hint is True else (need_hint or {})
        with open(CATEGORY, encoding="utf-8-sig") as f:
            self.cats = {r["pblancId"]: {c for c, v in r.items() if v == "1"} for r in csv.DictReader(f)}
    def search(self, query, k=10, user_gu="", stage="", need="", industry="", age="", industry_cat=""):
        question = query                # 특수 대상 판단은 원래 질문으로
        if need in self.need_hint:
            query = f"{query} {self.need_hint[need]}"
        cands = self.first.search(query, self.n, user_gu, stage)
        has_need = need and need != "미지정"
        user_cats = set(filter(None, industry_cat.split("|"))) if self.ind_penalty else set()
        if not has_need and not self.penalty and not user_cats:
            return cands[:k]
        score = self.scorer.scores(query)
        def adjusted(p):
            s = score[p]
            if has_need and need in self.cats.get(p, ()):
                s += self.bonus
            if self.penalty and (special_target(p, question, stage, industry, age)
                                 or (self.age_rule and age_mismatch(p, age))):
                s -= self.penalty
            if user_cats and industry_mismatch(p, user_cats):
                s -= self.ind_penalty
            return s
        ranked = sorted(cands, key=lambda p: -adjusted(p))
        return self.first.front(ranked, user_gu, stage)[:k]
