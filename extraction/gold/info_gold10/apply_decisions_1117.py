"""11/17 정예은 결정을 라벨링 CSV에 반영 (한 번만 실행)

1. 금리·자부담 줄 삭제 (안내정보에서 뺌)
2. 122273 제출서류 6~8번 대상: 원본 PDF 3쪽 표 기준
   "마이데이터 동의 시 개인은 생략 가능하나, 법인 신청시 6~8번 서류 제출"
   → 국세·지방세 완납증명서: 법인, 또는 마이데이터 비동의 시 / 4대보험료 완납증명원: 법인
3. 117673 기초·심화교육 "사업자등록증명원 또는 폐업사실증명원" → 두 줄
   (택1이지만 폐업 예정자는 사업자등록증명원, 폐업자는 폐업사실증명원으로 정해져 있음)
그 뒤 add_evidence.py를 다시 돌려 원문 문장을 붙인다
"""
import csv
from pathlib import Path

G = Path(__file__).resolve().parent
F = G / "info_라벨링.csv"
rows = list(csv.DictReader(open(F, encoding="utf-8-sig")))
cols = list(rows[0].keys())
n0 = len(rows)

rows = [r for r in rows if r["칸"] not in ("금리", "자부담")]
n1 = len(rows)

MD = "마이데이터 비동의 시"
for r in rows:
    if r["공고ID"].endswith("122273") and r["칸"] == "제출서류":
        if r["값"] in ("국세 완납증명서", "지방세 완납증명서"):
            r["대상"] = "법인, 또는 " + MD
            r["메모"] = "원본 PDF 3쪽: 마이데이터 동의 시 개인은 생략 가능, 법인은 6~8번 제출 (11/17 정예은 확인)"
        elif r["값"] == "4대보험료 완납증명원":
            r["대상"] = "법인"
            r["메모"] = "원본 PDF 3쪽: 법인 신청 시 제출 (11/17 정예은 확인)"

out = []
split = 0
for r in rows:
    if r["공고ID"].endswith("117673") and r["값"] == "사업자등록증명원 또는 폐업사실증명원":
        a, b = dict(r), dict(r)
        a.update(값="사업자등록증명원", 대상="폐업 예정자, " + MD, 메모="원문 '택1'이지만 폐업 예정자 서류 (11/17 정예은: 두 줄로 나눔)")
        b.update(값="폐업사실증명원", 대상="폐업자, " + MD, 메모="원문 '택1'이지만 폐업자 서류 (11/17 정예은: 두 줄로 나눔)")
        out += [a, b]
        split += 1
    else:
        out.append(r)

with open(F, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(out)
print(f"{n0}줄 → 금리·자부담 삭제 {n0 - n1}줄 → 117673 두 줄로 {split}곳 → {len(out)}줄")
