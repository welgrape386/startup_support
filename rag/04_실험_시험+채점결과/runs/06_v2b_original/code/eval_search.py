"""
3단계: 채점 — 검색기(V0, V1 …)를 답안지로 채점

사용법:  python eval_search.py
결과: runs/{번호}_{TAG}/ 폴더에 저장 (번호 = 실험기록.md의 #번호)
  runs_{TAG}_{날짜}.csv        질문 × 버전별 점수
  compare_{TAG}_{날짜}.xlsx    눈으로 보는 비교표 (요약 / 유형별 / 질문별 상위5)
  code/                        그때의 retrievers.py · eval_search.py · 답안지 복사본
지표 (1차와 같은 정의):
  Recall@5 = 상위 5개 안에 들어온 정답 수 / 그 질문의 정답 수 (정답 = 1점 이상)
  MRR      = 1 / 첫 정답의 등수
  nDCG@5   = 2점 정답이 1점 정답보다 위에 있는지까지 반영 (1이 최고)
"""
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from retrievers import V0, V1, Hybrid, RegionFilter, original_passages, DOC_BY_ID

# ── 실험 설명: 실행 전에 이 세 줄만 바꾸면 실험기록.md에 새 번호로 자동 추가됨 ──
TAG    = "v2b_original"                      # 파일 이름용 짧은 이름
TITLE  = "원문 문단 검색 V2b"                  # 실험 제목
WHY    = "#5에서 D 자격 유형이 가장 낮고 Q19는 모든 버전 0 → 사업개요에 자격 조건이 거의 없음. 사업개요만으로 채점이 애매해 원문을 봐야 했던 공고도 여럿(농식품 크라우드펀딩 등)"
CHANGE = "검색 대상을 공고명+사업개요 1조각 → 사업개요 + 원문 문단(약 500자, 공고명 붙임) 4,869조각으로 교체. 공고 점수 = 가장 높은 문단 점수. 하이브리드·지역 필터는 그대로"
LOG    = True                              # False면 기록 안 함 (코드 테스트용)

HERE = Path(__file__).resolve().parent
RAG = HERE.parent
QS = pd.read_csv(RAG / "03_평가셋_문제+답안지" / "search_questions.csv", encoding="utf-8-sig", dtype=str).fillna("")
POOL = pd.read_excel(RAG / "03_평가셋_문제+답안지" / "pool_snap1016.xlsx", sheet_name="답안지")
RUNS = HERE / "runs"; RUNS.mkdir(exist_ok=True)
LOGFILE = HERE / "실험기록.md"

import re
_n = max([int(x) for x in re.findall(r"^## #(\d+)", LOGFILE.read_text(encoding="utf-8"), re.M)] or [0]) + 1
RUN_DIR = RUNS / (f"{_n:02d}_{TAG}" if LOG else f"_test_{TAG}")   # 테스트 실행은 _test_ 폴더

# 답안지: 질문별 {공고ID: 점수}
label = {}
for _, r in POOL.iterrows():
    label.setdefault(r.qid, {})[r.pblancId] = int(r.score)
gold = {q: {p: s for p, s in d.items() if s >= 1} for q, d in label.items()}

def recall5(rk, g): return len(set(rk[:5]) & set(g)) / len(g)
def rr(rk, g):      return next((1 / i for i, p in enumerate(rk, 1) if p in g), 0.0)
def ndcg5(rk, g):
    dcg  = sum(g.get(p, 0) / np.log2(i + 1) for i, p in enumerate(rk[:5], 1))
    idcg = sum(s / np.log2(i + 1) for i, s in enumerate(sorted(g.values(), reverse=True)[:5], 1))
    return dcg / idcg

MARK = {2: "✅2", 1: "☑1", 0: "✗0"}
def show(qid, pid):
    s = label[qid].get(pid)
    return f'{MARK.get(s, "?미채점")} {DOC_BY_ID[pid]["pblancNm"][:38]}'

# ── 검색기 등록: 새 버전을 만들면 여기에 한 줄 추가 ───────────────
# 모든 검색기는 (질문 한 줄) → 공고ID 상위 10개 를 돌려줌
# 사용자 구(q.region)는 지금은 질문지 값을 씀. 실제 서비스에선 민지님 사용자 조건 추출 결과로 대체
print("검색기 준비 중...")
# 이번 실험(#6)에 필요한 것만: 기준(#5 하이브리드+지역) vs 원문 문단 버전
v0, v1 = V0(), V1()
hyr = RegionFilter(Hybrid(v0, v1))                                     # #5 기준선
P = original_passages()                                                # 사업개요 + 원문 v8 문단
v0o, v1o = V0(P), V1(P, "emb_v2b_v8_passage500.npy")
SEARCHERS = [
    ("하이브리드+지역",      lambda q: hyr.search(q.question, 10, q.region)),            # 기준 (#5)
    ("V0원문+지역",         lambda q: RegionFilter(v0o).search(q.question, 10, q.region)),
    ("V1원문+지역",         lambda q: RegionFilter(v1o).search(q.question, 10, q.region)),
    ("하이브리드원문+지역",  lambda q: RegionFilter(Hybrid(v0o, v1o)).search(q.question, 10, q.region)),  # V2b
]

res, top5 = [], []
for _, q in QS.iterrows():
    g = gold.get(q.qid)
    if not g:
        print(f"{q.qid}: 정답 0개 → 제외"); continue
    row5 = {"qid": q.qid, "유형": q.difficulty, "질문": q.question, "정답수": len(g)}
    for name, search in SEARCHERS:
        rk = search(q)
        res.append({"ver": name, "qid": q.qid, "difficulty": q.difficulty, "need": q.need,
                    "Recall@5": recall5(rk, g), "MRR": rr(rk, g), "nDCG@5": ndcg5(rk, g),
                    "정답수": len(g), "미채점_top5": sum(p not in label[q.qid] for p in rk[:5]),
                    "top10": " | ".join(rk)})
        row5[name] = "\n".join(f"{i}. {show(q.qid, p)}" for i, p in enumerate(rk[:5], 1))
    top5.append(row5)

res = pd.DataFrame(res)
stamp = datetime.now().strftime("%m%d_%H%M")
RUN_DIR.mkdir(exist_ok=True)
res.to_csv(RUN_DIR / f"runs_{TAG}_{stamp}.csv", index=False, encoding="utf-8-sig")

# 그때의 코드 + 답안지를 그대로 복사해둠 → 나중에 이 폴더만 보면 같은 실험을 다시 돌릴 수 있음
import shutil
SNAP = RUN_DIR / "code"
SNAP.mkdir(exist_ok=True)
for f in [HERE / "retrievers.py", Path(__file__),
          RAG / "03_평가셋_문제+답안지" / "pool_snap1016.xlsx"]:
    shutil.copy2(f, SNAP / f.name)

M = ["Recall@5", "MRR", "nDCG@5"]
summary = res.groupby("ver")[M].mean().round(3)
by_type = res.pivot_table(index="difficulty", columns="ver", values="Recall@5").round(2)
by_type.index = by_type.index.map({"A": "A 직접표현", "B": "B 우회표현", "C": "C 지역", "D": "D 자격"})
per_q = res.pivot_table(index="qid", columns="ver", values=M).round(2)
per_q.columns = [f"{v}_{m}" for m, v in per_q.columns]

# ── 비교표 엑셀 ───────────────────────────────────────────────
from openpyxl.styles import Alignment, Font
out = RUN_DIR / f"compare_{TAG}_{stamp}.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as xw:
    summary.to_excel(xw, sheet_name="요약")
    by_type.to_excel(xw, sheet_name="유형별_Recall@5")
    per_q.to_excel(xw, sheet_name="질문별_점수")
    t5 = pd.DataFrame(top5).merge(per_q.reset_index(), on="qid")
    t5.to_excel(xw, sheet_name="질문별_상위5", index=False)
    ws = xw.sheets["질문별_상위5"]
    for col, w in zip("ABCDEFGHIJ", [6, 5, 40, 6, 45, 45, 45, 45, 45, 45]):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
    for c in ws[1]: c.font = Font(bold=True)

print(f"\n저장: {out.name}\n\n=== 전체 ===\n{summary}\n\n=== 유형별 Recall@5 ===\n{by_type}")
print("\n미채점 공고가 상위5에 들어온 경우:", int(res["미채점_top5"].sum()), "건 (0이어야 공정)")
# 미채점이 있으면 목록 출력 → 답안지에 추가 채점 필요
unjudged = sorted({(r.qid, p) for _, r in res.iterrows()
                   for p in r.top10.split(" | ")[:5] if p not in label[r.qid]})
for qid, p in unjudged:
    print(f"  미채점: {qid} {p} {DOC_BY_ID[p]['pblancNm'][:40]}")


# ── 실험기록.md에 새 번호로 추가 (이전 기록은 건드리지 않음) ─────────
def md_table(df, index_name, digits=3):
    df = df.reset_index().rename(columns={df.index.name or "index": index_name})
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join(f"{v:.{digits}f}" if isinstance(v, float) else str(v) for v in row) + " |"
            for row in df.itertuples(index=False)]
    return "\n".join([head, sep] + body)

if LOG:
    path = LOGFILE
    text = path.read_text(encoding="utf-8")
    n = _n
    day = datetime.now().strftime("%m/%d")
    TYPES = {"A": "A 직접표현", "B": "B 우회표현", "C": "C 지역", "D": "D 자격"}
    def by(metric):
        t = res.pivot_table(index="difficulty", columns="ver", values=metric).round(2)
        t = t[[n_ for n_, _ in SEARCHERS]]
        t.index = t.index.map(TYPES)
        return md_table(t, "유형", 2)
    status = f" (⏳ 잠정: 상위5 미채점 {len(unjudged)}쌍)" if unjudged else ""
    block = f"""
---

## #{n} · {day} · {TITLE}{status}

**왜**: {WHY}
**바꾼 것**: {CHANGE}
**결과 폴더**: runs/{RUN_DIR.name}/ (비교표 {out.name}, 코드·답안지 복사본 code/)

전체

{md_table(summary.loc[[n_ for n_, _ in SEARCHERS]], "버전")}

유형별 Recall@5

{by("Recall@5")}

유형별 MRR

{by("MRR")}

유형별 nDCG@5

{by("nDCG@5")}

메모
- (결과 보고 해석 적기)
- **다음**:
"""
    # 맨 위 '한눈에 보기' 표에 한 줄 추가
    recall = " · ".join(f"{v} {summary.loc[v, 'Recall@5']:.3f}" for v, _ in SEARCHERS)
    row = f"| {n} | {day} | {TITLE}{' ⏳잠정' if unjudged else ''} | {recall} | {len(unjudged)} |"
    lines = text.split("\n")
    i = lines.index("## 한눈에 보기 (Recall@5)") + 1
    last = i
    while i < len(lines) and not lines[i].startswith(("## ", "---")):
        if lines[i].startswith("| "): last = i
        i += 1
    lines.insert(last + 1, row)
    path.write_text("\n".join(lines).rstrip("\n") + "\n" + block, encoding="utf-8")
    print(f"\n실험기록.md에 #{n} 추가 → 메모(해석·다음)만 직접 채우기")
