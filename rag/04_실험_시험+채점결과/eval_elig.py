"""
자격 문단 검색률: 정답 공고의 근거 문단이 자격 조건 문단인 비율

    python eval_elig.py      → runs/elig/elig_날짜.csv

- 대상: 상위 20개 안에 든 정답 공고 (통합공고 제외)
- 자격 문단: '신청자격·지원대상' 같은 제목 줄과 아래 5줄이 들어 있는 문단
  제목 줄 = 30자 이하이거나 키워드 뒤에 ':'가 오는 줄
- @1: 가장 가까운 문단 1개가 자격 문단 / @3: 3개 안에 자격 문단
- 비교: 질문만으로 고르기(evidence), 질문 + 자격 단어로 고르기(elig_evidence), 무작위
"""
import re
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from retrievers import V0, V1, Hybrid, RegionFilter, NeedBoost, clean_passages, tokenize, GUIDE_IDS, TEXTS, RAG
from search_service import ELIG_HINT

HERE = Path(__file__).resolve().parent
ELIG = re.compile(r"신청\s*자격|지원\s*대상|모집\s*대상|사업\s*대상|참여\s*대상|자격\s*요건|신청\s*대상")
WINDOW, TITLE_LEN = 5, 30

def elig_lines(pid):
    """자격 제목 줄과 아래 줄들 (10자 이상만)"""
    f = TEXTS / f"{pid}.txt"
    if not f.exists():
        return []
    lines = [l.strip() for l in f.read_text(encoding="utf-8").splitlines()]
    keep = set()
    for i, l in enumerate(lines):
        m = ELIG.search(l)
        if m and (len(l) <= TITLE_LEN or re.match(r"\s*[:：]", l[m.end():])):
            keep.update(range(i, min(i + WINDOW, len(lines))))
    return [lines[i] for i in sorted(keep) if len(lines[i]) >= 10]

CT, CO, rows = clean_passages()
v1 = V1((CT, CO), rows=rows)
v0 = V0((CT, CO))
hy = Hybrid(v0, v1)
engine = NeedBoost(RegionFilter(hy, demote_other_gu=5, stage_aware=True, drop_guide=True), hy, special_penalty=0.01)

by_doc = {}
for i, pid in enumerate(CO):
    by_doc.setdefault(pid, []).append(i)
is_elig = {}
for pid, idx in by_doc.items():
    el = elig_lines(pid)
    for i in idx:
        is_elig[i] = CT[i].startswith("[") and any(l in CT[i] for l in el)

QS = pd.read_csv(RAG / "03_평가셋_문제+답안지" / "search_questions.csv", encoding="utf-8-sig", dtype=str).fillna("")
POOL = pd.read_excel(RAG / "03_평가셋_문제+답안지" / "pool_snap1016.xlsx", sheet_name="답안지")
gold = {}
for _, r in POOL.iterrows():
    if r.score >= 1 and r.pblancId not in GUIDE_IDS:
        gold.setdefault(r.qid, set()).add(r.pblancId)

res = []
for _, q in QS.iterrows():
    if q.qid not in gold:
        continue
    top = engine.search(q.question, 20, q.region, q.stage, q.need, q.industry, q.age)
    sims = v1._sims(q.question)
    sims_h = v1._sims(q.question + ELIG_HINT)
    bm = v0.bm.get_scores(tokenize(q.question))
    for p in top:
        if p not in gold[q.qid]:
            continue
        idx = by_doc[p]
        if not any(is_elig[i] for i in idx):      # 원문이 없거나 자격 문단을 못 찾은 공고
            res.append({"qid": q.qid, "유형": q.difficulty, "pblancId": p, "자격문단있음": False})
            continue
        n, k = len(idx), sum(is_elig[i] for i in idx)
        by_sim = sorted(idx, key=lambda i: -sims[i])
        by_h = sorted(idx, key=lambda i: -sims_h[i])
        by_bm = sorted(idx, key=lambda i: -bm[i])
        res.append({"qid": q.qid, "유형": q.difficulty, "pblancId": p, "자격문단있음": True,
                    "의미@1": is_elig[by_sim[0]], "의미@3": any(is_elig[i] for i in by_sim[:3]),
                    "자격단어@1": is_elig[by_h[0]], "자격단어@3": any(is_elig[i] for i in by_h[:3]),
                    "키워드@1": is_elig[by_bm[0]],
                    "무작위@1": k / n, "무작위@3": 1 - np.prod([(n - k - j) / (n - j) for j in range(3)]) if n - k >= 3 else 1.0,
                    "근거문단": CT[by_sim[0]].split("\n", 1)[-1][:120].replace("\n", " ")})

df = pd.DataFrame(res)
out = HERE / "runs" / "elig" / f"elig_{datetime.now():%m%d_%H%M}.csv"
out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out, index=False, encoding="utf-8-sig")
ok = df[df.자격문단있음]
print(f"정답 공고 {len(df)}쌍 중 자격 문단을 찾은 {len(ok)}쌍으로 계산\n")
for name, part in [("전체", ok), ("D 자격 질문", ok[ok.유형 == "D"])]:
    print(f"[{name}] {len(part)}쌍")
    print(f"  @1  질문만 {part['의미@1'].mean():.1%} / 자격단어 {part['자격단어@1'].mean():.1%} / 무작위 {part['무작위@1'].mean():.1%}")
    print(f"  @3  질문만 {part['의미@3'].mean():.1%} / 자격단어 {part['자격단어@3'].mean():.1%} / 무작위 {part['무작위@3'].mean():.1%}")
print(f"\n저장: {out.name}")
