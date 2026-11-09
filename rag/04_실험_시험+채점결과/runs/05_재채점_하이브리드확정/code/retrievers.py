"""
검색기 모음 (응시자). 검색 대상 = 02_검색대상_시험지/docs_snap1016.jsonl (342건)
- V0: BM25 키워드 검색
- V1: bge-m3 의미 검색
V0·V1은 API 필드(공고명 + 사업개요)만 사용. 원문은 V2부터.
"""
import json
from pathlib import Path
import numpy as np

RAG   = Path(__file__).resolve().parent.parent
DATA  = RAG / "02_검색대상_시험지" / "docs_snap1016.jsonl"
CACHE = RAG / "04_실험_시험+채점결과" / "cache"

DOCS = [json.loads(l) for l in open(DATA, encoding="utf-8")]
IDS = [d["pblancId"] for d in DOCS]
DOC_BY_ID = dict(zip(IDS, DOCS))

def doc_text(d):
    return f'{d["pblancNm"]}\n{d["summary"]}'


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
    def __init__(self):
        from rank_bm25 import BM25Okapi
        self.bm = BM25Okapi([tokenize(doc_text(d)) for d in DOCS])
    def search(self, query, k=10):
        scores = self.bm.get_scores(tokenize(query))
        return [IDS[i] for i in np.argsort(-scores)[:k]]


# ── V1: 의미 검색 ───────────────────────────────────────────
class V1:
    def __init__(self, model="BAAI/bge-m3"):
        from sentence_transformers import SentenceTransformer
        self.m = SentenceTransformer(model)
        CACHE.mkdir(parents=True, exist_ok=True)
        path = CACHE / "emb_v1_snap1016.npy"          # 1차 임베딩(488건)과 섞이지 않게 새 이름
        if path.exists():
            self.E = np.load(path)
        else:
            self.E = self.m.encode([doc_text(d) for d in DOCS], normalize_embeddings=True,
                                   batch_size=16, show_progress_bar=True)
            np.save(path, self.E)
        assert len(self.E) == len(DOCS), "임베딩 수와 공고 수가 다름 → cache 파일 지우고 다시 실행"
    def search(self, query, k=10):
        q = self.m.encode([query], normalize_embeddings=True)[0]
        return [IDS[i] for i in np.argsort(-(self.E @ q))[:k]]


# ── V1.5: 하이브리드 (V0 + V1 순위 합치기, RRF) ─────────────────
class Hybrid:
    """RRF(Reciprocal Rank Fusion): 공고 점수 = 1/(K + V0 순위) + 1/(K + V1 순위)
    - 두 검색기 점수는 단위가 달라서(BM25 점수 vs 코사인 유사도) 그대로 더할 수 없음 → 순위만 사용
    - K=60은 RRF 논문 기본값. 클수록 1등과 10등의 점수 차이가 작아짐"""
    def __init__(self, v0, v1, K=60):
        self.v0, self.v1, self.K = v0, v1, K
    def search(self, query, k=10):
        score = {}
        for ranked in (self.v0.search(query, len(IDS)), self.v1.search(query, len(IDS))):
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
        self.base = base                       # V0 또는 V1
    def search(self, query, k=10, user_gu=""):
        ranked = self.base.search(query, len(IDS))          # 전체 순위를 받아서
        return [p for p in ranked if region_ok(p, user_gu)][:k]   # 못 쓰는 것 빼고 상위 k
