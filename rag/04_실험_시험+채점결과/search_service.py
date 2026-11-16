"""
백엔드에서 부르는 검색

    from search_service import search
    search("마포구에서 디저트 카페를 준비하는 예비창업자예요", user_gu="마포구", stage="예비", need="홍보·판매")

인자 (모르면 "")
- user_gu  : 서울 구 이름 (예: "마포구")
- stage    : "예비" / "개업"
- need     : 자금, 교육·컨설팅, 공간·시설, 홍보·판매, 인력, 기술개발, 해외진출, 제도·인증, 기타, 미지정 중 하나
- industry : 업종 (예: "디저트 카페")
- age      : 나이
- k        : 판정으로 넘길 개수, 기본 20

결과 (순서는 rank 기준. score는 순위 계산용이라 화면에 쓰지 않음)
- pblancId, rank, score
- evidence      : 질문과 가장 가까운 문단
- evidence_from : "원문" / "사업개요"
- elig_evidence : 자격 조건이 있을 법한 문단
처음 부를 때 모델을 불러와서 수십 초 걸림
"""
from retrievers import V0, V1, Hybrid, RegionFilter, NeedBoost, clean_passages

SEARCH_TOP_K = 20
ELIG_HINT = " 신청자격 지원대상 신청대상"
DROP_GUIDE = True
_engine = None

def _load():
    global _engine
    if _engine is None:
        CT, CO, rows = clean_passages()
        v1 = V1((CT, CO), rows=rows)
        hy = Hybrid(V0((CT, CO)), v1)
        region = RegionFilter(hy, demote_other_gu=5, stage_aware=True, drop_guide=DROP_GUIDE)
        _engine = (hy, v1, NeedBoost(region, hy, n=SEARCH_TOP_K, special_penalty=0.01))
    return _engine

def _strip(text):
    """원문 문단 앞의 [공고명] 줄 떼기"""
    return text.split("\n", 1)[1] if text.startswith("[") else text

def search(query, user_gu="", k=SEARCH_TOP_K, stage="", need="", industry="", age=""):
    hy, v1, engine = _load()
    ranked = engine.search(query, k, user_gu, stage, need, industry, str(age or ""))
    score = hy.scores(query)
    best = v1.best_passages(query)
    best_elig = v1.best_passages(query + ELIG_HINT)
    return [{"pblancId": pid, "rank": r, "score": round(score[pid], 6),
             "evidence": _strip(best[pid]),
             "evidence_from": "원문" if best[pid].startswith("[") else "사업개요",
             "elig_evidence": _strip(best_elig[pid])}
            for r, pid in enumerate(ranked, 1)]


if __name__ == "__main__":
    q = "29살이고 마포구에서 디저트 카페를 준비하는 예비창업자예요. 오픈하면 라이브커머스로도 판매해보고 싶어요."
    for x in search(q, "마포구", 5, stage="예비", need="홍보·판매"):
        print(x["rank"], x["pblancId"], x["evidence_from"], x["evidence"][:60].replace("\n", " "))
