"""
검색기 모음 (응시자). 검색 대상 = 02_검색대상_시험지/docs_snap1016.jsonl (342건)

블록을 조합해서 버전을 만든다
  V0  키워드 검색 (BM25)          ┐
  V1  의미 검색 (bge-m3)          ├─ Hybrid (V1.5, 순위 합치기) ─ RegionFilter (V2a, 지역 거르기)
  passages: 무엇을 검색하나        ┘
    - summary_passages()  공고 1건 = 공고명+사업개요 1조각   (V0·V1·V1.5·V2a)
    - original_passages() 공고 1건 = 사업개요 + 원문 문단 여러 조각 (V2b)
    - clean_passages()    위에서 잡음 문단(제외업종 표·서식·연락처)을 뺀 것 (V2b-2)
문단이 여러 개면 공고 점수 = 그 공고 문단 중 가장 높은 점수 (MaxP)
"""
import json, re
from pathlib import Path
import numpy as np

RAG   = Path(__file__).resolve().parent.parent
DATA  = RAG / "02_검색대상_시험지" / "docs_snap1016.jsonl"
TEXTS = RAG / "01_원본" / "texts_v8_20261024" / "texts"     # 원문 v8 (10/24)
CACHE = RAG / "04_실험_시험+채점결과" / "cache"

DOCS = [json.loads(l) for l in open(DATA, encoding="utf-8")]
IDS = [d["pblancId"] for d in DOCS]
DOC_BY_ID = dict(zip(IDS, DOCS))


# ── 검색 대상 조각(passage) 만들기 ───────────────────────────────
def summary_passages():
    """공고 1건 = 조각 1개 (공고명 + 사업개요). 반환: (조각 텍스트 목록, 각 조각의 공고ID 목록)"""
    return [f'{d["pblancNm"]}\n{d["summary"]}' for d in DOCS], list(IDS)

def split_text(text, size=500):
    """원문을 약 size 글자 단위 문단으로 자름. 줄 단위로 모으다가 size를 넘으면 새 조각
    (문장 중간에서 끊기지 않게 줄 경계에서 자름. 한 줄이 너무 길면 그 줄은 size 단위로 자름)"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    chunks, cur = [], ""
    for line in lines:
        while len(line) > size:                       # 아주 긴 줄
            if cur: chunks.append(cur); cur = ""
            chunks.append(line[:size]); line = line[size:]
        if len(cur) + len(line) + 1 > size and cur:
            chunks.append(cur); cur = ""
        cur = f"{cur}\n{line}" if cur else line
    if cur: chunks.append(cur)
    return [c for c in chunks if len(c) >= 30]        # 너무 짧은 조각(쪽번호 등) 제외

def original_passages(size=500):
    """공고 1건 = 사업개요 조각 1개 + 원문 문단 여러 개
    - 조각마다 앞에 공고명을 붙임 (문단만 보면 어느 공고인지 모르니까)
    - 원문이 없는 33건은 사업개요 조각만"""
    texts, owners = summary_passages()
    for d in DOCS:
        f = TEXTS / f'{d["pblancId"]}.txt'
        if not d["has_text"] or not f.exists():
            continue
        for c in split_text(f.read_text(encoding="utf-8"), size):
            texts.append(f'[{d["pblancNm"]}]\n{c}')
            owners.append(d["pblancId"])
    return texts, owners

# ── V2b-2: 잡음 문단 거르기 ─────────────────────────────────────
# 원문에는 지원 내용과 상관없는 문단(제외업종 표, 신청서 양식, 연락처 목록)이 많고,
# 이 문단이 업종 이름·'세무'·'운영' 같은 단어 때문에 질문과 엉뚱하게 맞음 → 검색 대상에서 뺌
_CODE  = re.compile(r'(?<![\d.,~\-])\d{2,5}(?![\d.,%년월일개원명세시분])')   # 업종코드처럼 보이는 숫자
_PHONE = re.compile(r'\d{2,4}\)?[-‐ ]\d{3,4}[-‐]\d{4}')                       # 전화번호
_IND   = re.compile(r'표준산업분류|업종코드|제외 ?업종|제한 ?업종|보증제한|지원제외업종|융자제외')
_ELIG  = re.compile(r'신청 ?자격|지원 ?대상|모집 ?대상|자격 ?요건|신청 ?대상|참여 ?대상')
_FORM  = re.compile(r'성 ?명|생년월일|연락처|서명|\(인\)|동의합니다|휴대폰|이메일|주소')
_SIGN  = re.compile(r'동의|서명|\(인\)|신청서|서식|양식')

def noise_type(passage):
    """잡음 문단이면 종류('업종표'/'서식'/'연락처'), 아니면 None"""
    b = passage.split("\n", 1)[1] if passage.startswith("[") else passage   # 앞의 [공고명] 줄은 빼고 판단
    code = len(_CODE.findall(b))
    if code >= 8 and (_IND.search(b) or code >= 15):
        return "업종표"                                # 업종코드가 줄줄이 나오는 표
    if _ELIG.search(b):
        return None                                    # 신청자격·지원대상 설명이 있으면 남김 (안전장치)
    if b.count("□") >= 6 or (len(_FORM.findall(b)) >= 4 and _SIGN.search(b)):
        return "서식"                                  # 체크박스·개인정보 동의서·신청서 양식
    if len(_PHONE.findall(b)) >= 3:
        return "연락처"                                # 지점·센터 연락처 목록
    return None

def clean_passages(size=500):
    """original_passages()에서 잡음 문단을 뺀 것. rows = 원래 목록에서 남긴 위치 (임베딩 재사용용)
    사업개요 조각(앞 342개)은 항상 남김"""
    texts, owners = original_passages(size)
    rows = [i for i, t in enumerate(texts) if i < len(DOCS) or noise_type(t) is None]
    return [texts[i] for i in rows], [owners[i] for i in rows], rows

def _to_doc_ranking(scores, owners):
    """조각 점수 → 공고 순위 (공고 점수 = 가장 높은 조각 점수)
    조각을 점수순으로 정렬한 뒤 공고가 처음 나오는 순서대로 나열 = 공고별 최고 조각 기준 순위
    (np.argsort 사용: 동점 순서까지 리팩토링 전 코드와 같게 유지 → #5 결과 그대로 재현)"""
    seen, ranking = set(), []
    for i in np.argsort(-np.asarray(scores)):
        pid = owners[i]
        if pid not in seen:
            seen.add(pid); ranking.append(pid)
    return ranking


# ── V0: 키워드 검색 ─────────────────────────────────────────
_kiwi = None
def tokenize(text):
    # 명사·동사·형용사 어간·영어·숫자만 남김 (1차와 동일)
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return [t.form for t in _kiwi.tokenize(text)
            if t.tag.startswith(("NN", "VV", "VA", "XR", "SL", "SN"))]

class V0:
    def __init__(self, passages=None):
        from rank_bm25 import BM25Okapi
        self.texts, self.owners = passages or summary_passages()
        self.bm = BM25Okapi([tokenize(t) for t in self.texts])
    def search(self, query, k=10):
        return _to_doc_ranking(self.bm.get_scores(tokenize(query)), self.owners)[:k]


# ── V1: 의미 검색 ───────────────────────────────────────────
_model = None
def bge_m3():
    global _model                                     # 모델은 한 번만 불러서 같이 씀 (2GB)
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("BAAI/bge-m3")
    return _model

class V1:
    def __init__(self, passages=None, cache_name="emb_v1_snap1016.npy", rows=None):
        """rows: 캐시(전체 문단 임베딩) 중 이번에 쓸 위치만 골라 씀 → 문단을 빼기만 할 땐 다시 계산할 필요 없음"""
        self.texts, self.owners = passages or summary_passages()
        self.m = bge_m3()
        CACHE.mkdir(parents=True, exist_ok=True)
        path = CACHE / cache_name                     # 조각이 바뀌면 cache_name도 바꿔야 함
        if path.exists():
            self.E = np.load(path)
        else:
            self.E = self.m.encode(self.texts, normalize_embeddings=True,
                                   batch_size=16, show_progress_bar=True)
            np.save(path, self.E)
        if rows is not None:
            self.E = self.E[rows]
        assert len(self.E) == len(self.texts), f"임베딩 수와 조각 수가 다름 → cache/{cache_name} 지우고 다시 실행"
    def search(self, query, k=10):
        q = self.m.encode([query], normalize_embeddings=True)[0]
        return _to_doc_ranking(self.E @ q, self.owners)[:k]


# ── V1.5: 하이브리드 (두 검색기 순위 합치기, RRF) ─────────────────
class Hybrid:
    """RRF(Reciprocal Rank Fusion): 공고 점수 = 1/(K + A 순위) + 1/(K + B 순위)
    - 두 검색기 점수는 단위가 달라서(BM25 점수 vs 코사인 유사도) 그대로 더할 수 없음 → 순위만 사용
    - K=60은 RRF 논문 기본값. 클수록 1등과 10등의 점수 차이가 작아짐"""
    def __init__(self, a, b, K=60):
        self.a, self.b, self.K = a, b, K
    def search(self, query, k=10):
        score = {}
        for ranked in (self.a.search(query, len(IDS)), self.b.search(query, len(IDS))):
            for r, pid in enumerate(ranked, 1):
                score[pid] = score.get(pid, 0) + 1 / (self.K + r)
        return sorted(score, key=score.get, reverse=True)[:k]


# ── V2a: 지역 필터 (검색은 그대로, 결과에서 못 쓰는 공고만 뺌) ─────
def region_ok(pid, user_gu):
    """서울 사용자가 쓸 수 있는 공고인가
    - 타지역 공고 → 뺌
    - 서울 구 전용 공고 → 사용자 구를 알 때, 다른 구면 뺌 (구를 모르면 남김: 채점 규칙 ②와 같음)"""
    d = DOC_BY_ID[pid]
    if d["region"] == "타지역":
        return False
    if d["seoul_gu"] and user_gu and user_gu not in d["seoul_gu"]:
        return False
    return True

class RegionFilter:
    def __init__(self, base):
        self.base = base                       # 어떤 검색기든 (V0, V1, Hybrid …)
    def search(self, query, k=10, user_gu=""):
        ranked = self.base.search(query, len(IDS))          # 전체 순위를 받아서
        return [p for p in ranked if region_ok(p, user_gu)][:k]   # 못 쓰는 것 빼고 상위 k
