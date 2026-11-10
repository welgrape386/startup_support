"""
검색 채점

    python eval_search.py

새 실험: SEARCHERS 맨 아래에 한 줄 추가 → TAG·TITLE·WHY·CHANGE 수정 → LOG = True
결과는 runs/번호_TAG/ (점수 csv, 비교표 엑셀, 그때 코드 복사본)
LOG = True면 실험기록.md에 '지금 기본 vs 이번 버전'이 새 번호로 붙음

지표: Recall@5, Recall@20, MRR, nDCG@5 (정답 = 1점 이상, 통합공고는 0점)
"""
import re, shutil
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from openpyxl.styles import Alignment, Font
from retrievers import V0, V1, Hybrid, RegionFilter, NeedBoost, GUIDE_IDS, original_passages, clean_passages, DOC_BY_ID

TAG    = "test"
TITLE  = "(실험 제목)"
WHY    = "(왜)"
CHANGE = "(바꾼 것)"
LOG    = False

HERE = Path(__file__).resolve().parent
RAG = HERE.parent
QS = pd.read_csv(RAG / "03_평가셋_문제+답안지" / "search_questions.csv", encoding="utf-8-sig", dtype=str).fillna("")
POOL = pd.read_excel(RAG / "03_평가셋_문제+답안지" / "pool_snap1016.xlsx", sheet_name="답안지")
LOGFILE = HERE / "실험기록.md"
_n = max([int(x) for x in re.findall(r"^### #(\d+)", LOGFILE.read_text(encoding="utf-8"), re.M)] or [0]) + 1
RUN_DIR = HERE / "runs" / (f"{_n:02d}_{TAG}" if LOG else f"_test/{TAG}")

label = {}
for _, r in POOL.iterrows():
    label.setdefault(r.qid, {})[r.pblancId] = 0 if r.pblancId in GUIDE_IDS else int(r.score)
gold = {q: {p: s for p, s in d.items() if s >= 1} for q, d in label.items()}

def recall(rk, g, k): return len(set(rk[:k]) & set(g)) / len(g)
def rr(rk, g):        return next((1 / i for i, p in enumerate(rk, 1) if p in g), 0.0)
def ndcg5(rk, g):
    dcg  = sum(g.get(p, 0) / np.log2(i + 1) for i, p in enumerate(rk[:5], 1))
    idcg = sum(s / np.log2(i + 1) for i, s in enumerate(sorted(g.values(), reverse=True)[:5], 1))
    return dcg / idcg

# 검색 버전. 사용자 정보는 질문지 값을 씀 (서비스에서는 사용자 추출 결과)
print("검색기 준비 중...")
P = original_passages()
CT, CO, rows = clean_passages()
v0o, v1o = V0(P), V1(P)
v0c, v1c = V0((CT, CO)), V1((CT, CO), rows=rows)
hy = Hybrid(v0c, v1c)
K = 20
region = RegionFilter(hy, demote_other_gu=5, stage_aware=True)
region_g = RegionFilter(hy, demote_other_gu=5, stage_aware=True, drop_guide=True)
need = NeedBoost(region, hy)
special = NeedBoost(region, hy, special_penalty=0.01)
default = NeedBoost(region_g, hy, special_penalty=0.01)      # search_service.py와 같음

BASE = "지금 기본"
SEARCHERS = [
    ("기준선 (하이브리드+지역)",  lambda q: RegionFilter(Hybrid(v0o, v1o)).search(q.question, K, q.region)),
    ("원문 정제",              lambda q: RegionFilter(hy).search(q.question, K, q.region)),
    ("다른 구 미루기 (예비만)",  lambda q: region.search(q.question, K, q.region, q.stage)),
    ("원하는 지원 올리기",       lambda q: need.search(q.question, K, q.region, q.stage, q.need)),
    ("특수 대상 내리기",         lambda q: special.search(q.question, K, q.region, q.stage, q.need, q.industry, q.age)),
    (BASE,                    lambda q: default.search(q.question, K, q.region, q.stage, q.need, q.industry, q.age)),
    # 새 실험은 여기에
]
NEW = SEARCHERS[-1][0]

MARK = {2: "✅2", 1: "☑1", 0: "✗0"}
res, top5 = [], []
for _, q in QS.iterrows():
    g = gold.get(q.qid)
    if not g:
        print(f"{q.qid}: 정답 없음, 제외"); continue
    row5 = {"qid": q.qid, "유형": q.difficulty, "질문": q.question, "정답수": len(g)}
    for name, search in SEARCHERS:
        rk = search(q)
        res.append({"ver": name, "qid": q.qid, "difficulty": q.difficulty, "need": q.need,
                    "Recall@5": recall(rk, g, 5), "Recall@20": recall(rk, g, 20), "MRR": rr(rk, g), "nDCG@5": ndcg5(rk, g),
                    "정답수": len(g), "미채점_top5": sum(p not in label[q.qid] for p in rk[:5]), "top20": " | ".join(rk)})
        row5[name] = "\n".join(f'{i}. {MARK.get(label[q.qid].get(p), "?미채점")} {DOC_BY_ID[p]["pblancNm"][:38]}'
                               for i, p in enumerate(rk[:5], 1))
    top5.append(row5)

res = pd.DataFrame(res)
M = ["Recall@5", "Recall@20", "MRR", "nDCG@5"]
order = [n for n, _ in SEARCHERS]
summary = res.groupby("ver")[M].mean().round(3).loc[order]
TYPES = {"A": "A 직접표현", "B": "B 우회표현", "C": "C 지역", "D": "D 자격"}
by_type = res.pivot_table(index="difficulty", columns="ver", values="Recall@5").round(2)[order].rename(index=TYPES)
per_q = res.pivot_table(index="qid", columns="ver", values=M).round(2)
per_q.columns = [f"{v}_{m}" for m, v in per_q.columns]
unjudged = sorted({(r.qid, p) for _, r in res.iterrows() for p in r.top20.split(" | ")[:5] if p not in label[r.qid]})

# 저장
stamp = datetime.now().strftime("%m%d_%H%M")
RUN_DIR.mkdir(parents=True, exist_ok=True)
res.to_csv(RUN_DIR / f"runs_{TAG}_{stamp}.csv", index=False, encoding="utf-8-sig")
out = RUN_DIR / f"compare_{TAG}_{stamp}.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as xw:
    summary.to_excel(xw, sheet_name="요약")
    by_type.to_excel(xw, sheet_name="유형별_Recall@5")
    per_q.to_excel(xw, sheet_name="질문별_점수")
    pd.DataFrame(top5).to_excel(xw, sheet_name="질문별_상위5", index=False)
    ws = xw.sheets["질문별_상위5"]
    for i, col in enumerate(ws.columns):
        ws.column_dimensions[col[0].column_letter].width = [6, 5, 40, 6][i] if i < 4 else 45
    for row in ws.iter_rows(min_row=2):
        for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
    for c in ws[1]: c.font = Font(bold=True)
(RUN_DIR / "code").mkdir(exist_ok=True)
for f in [HERE / "retrievers.py", Path(__file__), RAG / "03_평가셋_문제+답안지" / "pool_snap1016.xlsx"]:
    shutil.copy2(f, RUN_DIR / "code" / f.name)

print(f"\n저장: {out}\n\n{summary}\n\n유형별 Recall@5\n{by_type}")
print(f"\n상위5 미채점 {len(unjudged)}쌍 (0이어야 공정)")
for qid, p in unjudged:
    print(f"  {qid} {p} {DOC_BY_ID[p]['pblancNm'][:40]}")

# 실험기록.md에 추가
if LOG:
    day = datetime.now().strftime("%m/%d")
    s, b = summary.loc[NEW], summary.loc[BASE]
    nums = lambda x: " / ".join(f"{x[m]:.3f}" for m in M)
    warn = f" (상위5 미채점 {len(unjudged)}쌍)" if unjudged else ""
    block = f"""
### #{_n} · {day} · {TITLE}{warn}
- **왜**: {WHY}
- **바꾼 것**: {CHANGE}
- **결과** (Recall@5 / Recall@20 / MRR / nDCG@5): 지금 기본 {nums(b)} → 이번 {nums(s)}
- **결론**:
- 자세한 표: `runs/{RUN_DIR.name}/`
"""
    row = f"| {_n} | {day} | {TITLE} | {s['Recall@5']:.3f} | {s['Recall@20']:.3f} | {s['MRR']:.3f} | |"
    lines = LOGFILE.read_text(encoding="utf-8").split("\n")
    i = next(j for j, l in enumerate(lines) if l.startswith("| #"))
    while i + 1 < len(lines) and lines[i + 1].startswith("|"):
        i += 1
    lines.insert(i + 1, row)
    LOGFILE.write_text("\n".join(lines).rstrip("\n") + "\n" + block, encoding="utf-8")
    print(f"\n실험기록.md에 #{_n} 추가. 결론만 채우기")
