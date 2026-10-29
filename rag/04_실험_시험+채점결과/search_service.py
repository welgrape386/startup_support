"""
백엔드 연결용 검색 (ver6 = 하이브리드 + 원문 정제 + 지역 필터, 다른 구 공고는 6위 아래로)

사용법:
  from search_service import search
  search("마포구에서 디저트 카페를 준비하는 예비창업자예요", user_gu="마포구")
  → [{"pblancId": "PBLN_…", "rank": 1, "score": 0.0325, "evidence": "…", "evidence_from": "원문"}, …]

- k: 판정으로 넘길 개수 (기본 20 = SEARCH_TOP_K, 10/28 요청사항 근거: 상위20 안에 정답 89%)
- user_gu: 사용자 서울 구 정식 명칭 (예: "마포구"). 모르면 "" → 구로 거르지 않음
- score: RRF 점수 (클수록 위). 순위 비교용이고 0~1 확률이 아님
- evidence: 그 공고에서 질문과 가장 가까운 문단 (의미 검색 기준, 화면의 "추천 근거"용)
- 처음 부를 때 문단 정리 + bge-m3 모델(약 2GB)을 불러와서 수십 초 걸림, 이후는 1초 안팎
"""
from retrievers import V0, V1, Hybrid, RegionFilter, clean_passages

SEARCH_TOP_K = 20
_engine = None

def _load():
    global _engine
    if _engine is None:
        CT, CO, rows = clean_passages()                                     # 사업개요 + 원문 문단 (잡음 제거) 3,897개
        v1 = V1((CT, CO), "emb_v2b_v8_passage500.npy", rows=rows)          # 임베딩은 cache/에 미리 계산해 둔 것
        hy = Hybrid(V0((CT, CO)), v1)
        _engine = (hy, v1, RegionFilter(hy, demote_other_gu=5))
    return _engine

def search(query, user_gu="", k=SEARCH_TOP_K):
    hy, v1, rf = _load()
    ranked = rf.search(query, k, user_gu)
    score = hy.scores(query)
    best = v1.best_passages(query)
    out = []
    for r, pid in enumerate(ranked, 1):
        text = best[pid]
        from_text = text.startswith("[")                                    # 원문 조각은 앞에 [공고명]이 붙어 있음
        out.append({"pblancId": pid, "rank": r, "score": round(score[pid], 6),
                    "evidence": text.split("\n", 1)[1] if from_text else text,
                    "evidence_from": "원문" if from_text else "사업개요"})
    return out


if __name__ == "__main__":
    for x in search("29살이고 마포구에서 디저트 카페를 준비하는 예비창업자예요. 오픈하면 라이브커머스로도 판매해보고 싶어요.", "마포구", 5):
        print(x["rank"], x["pblancId"], x["score"], x["evidence_from"], x["evidence"][:60].replace("\n", " "))
