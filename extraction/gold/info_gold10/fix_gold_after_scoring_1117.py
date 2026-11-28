"""11/17 채점 후 정답 수정 (한 번만 실행). 정답 초안이 원문을 보면 명백히 빠뜨린 것만 고침
LLM 결과를 본 뒤의 수정이라 보고서에 "채점 후 정답 오류 5개 수정"으로 적는다

1. 121291 전문상담 트랙 지원규모 "제한 없음" (원문 "※ (전문상담) 제한 없음"). 초안은 최상위 "(현장클리닉) 3천건"만 있어 전문상담도 3천건으로 채점됨
2. 127098 창업기업확인서 (필수): "신청 접수 마감일까지 창업기업확인서를 제출하지 못하는 경우 신청 제외"
3. 127098 관련 확약서·증빙자료 (선택, 가점 받으려면): 가점 증빙은 선택 서류로 넣는 규칙
4. 119938 실적 증빙자료 (필수, 실적을 적은 경우): "상기 실적자료는 작성된 건수에 대하여 증빙자료를 추가로 제출해야 함"
5. 119938 기업부설연구소·연구개발전담부서 신고확인서 (필수, ①② 체크 시): "①,② 체크시 … 신고확인서 제출요청"
"""
import csv
from pathlib import Path

G = Path(__file__).resolve().parent
F = G / "info_라벨링.csv"
rows = list(csv.DictReader(open(F, encoding="utf-8-sig")))
cols = list(rows[0].keys())
P = "PBLN_000000000"
names = {r["공고ID"]: r["공고명"] for r in rows}
MEMO = "11/17 채점 후 정답 수정 (초안이 빠뜨림)"


def row(pid, 칸, 값, 트랙="", **kw):
    r = {c: "" for c in cols}
    r.update(공고ID=P + pid, 공고명=names[P + pid], 칸=칸, 값=값, 트랙=트랙, 메모=MEMO, **kw)
    return r


new = [
    row("121291", "지원규모", "제한 없음", "전문상담"),
    row("127098", "제출서류", "창업기업확인서", 필수="O"),
    row("127098", "제출서류", "관련 확약서·증빙자료", 필수="X", 대상="가점 받으려면"),
    row("119938", "제출서류", "실적 증빙자료", 필수="O", 대상="사업계획서에 기술개발·수상 실적을 적은 경우"),
    row("119938", "제출서류", "기업부설연구소·연구개발전담부서 신고확인서", 필수="O", 대상="사업계획서에 ①공인된 기업부설연구소 ②연구개발전담부서 보유를 체크한 경우"),
]
have = {(r["공고ID"], r["트랙"], r["칸"], r["값"]) for r in rows}
added = [r for r in new if (r["공고ID"], r["트랙"], r["칸"], r["값"]) not in have]


# 같은 공고·칸 줄 뒤에 끼워 넣음
def key(r):
    return r["공고ID"]


out = []
for r in rows:
    out.append(r)
for a in added:
    idx = max(i for i, r in enumerate(out) if r["공고ID"] == a["공고ID"] and (r["칸"] == a["칸"] or r["칸"] < "zz"))
    out.insert(idx + 1, a)
with open(F, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(out)
print(f"{len(rows)}줄 → {len(out)}줄 (추가 {len(added)})")
