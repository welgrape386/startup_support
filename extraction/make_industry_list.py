"""서비스 데이터의 업종명 키워드를 한 줄씩 모은 목록을 만든다 (11/13, 판정 담당 확인용)

사용법: python make_industry_list.py
입력: results/service_v4_업종확장/, results/service_v4/출처.csv, docs/target_seoul_national_62.csv
출력: results/service_v4_업종확장/업종명_목록.csv
- 칸: 공고ID, 공고명, 출처(정답셋/LLM), 위치(최상위/트랙: 이름), 구분(허용/제외/제외_예외/제외_목록), 업종명, 제외_참조
- 제외_목록(CSV에서 복사한 업종)은 한 줄에 개수만 적는다
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
S = ROOT / "results/service_v4_업종확장"


def main():
    src = {r["공고ID"]: ("정답셋" if r["출처"].startswith("정답셋") else "LLM")
           for r in csv.DictReader(open(ROOT / "results/service_v4/출처.csv", encoding="utf-8-sig"))}
    title = {r["공고ID"]: r["공고명"] for r in csv.DictReader(open(ROOT / "docs/target_seoul_national_62.csv", encoding="utf-8-sig"))}
    rows = []
    for pid in sorted(src):
        j = json.loads((S / f"{pid}.json").read_text(encoding="utf-8"))
        cells = [("최상위", j["업종"])] + [(f"트랙: {t['이름']}", t["조건"]["업종"]) for t in j.get("트랙") or []
                                          if "업종" in (t.get("조건") or {})]
        n = 0
        for where, c in cells:
            nm = c.get("업종명") or {}
            base = {"공고ID": pid, "공고명": title.get(pid, ""), "출처": src[pid], "위치": where,
                    "제외_참조": c.get("제외_참조") or ""}
            for side in ("허용", "제외", "제외_예외"):
                for w in nm.get(side) or []:
                    rows.append({**base, "구분": side, "업종명": w})
                    n += 1
            if nm.get("제외_목록"):
                rows.append({**base, "구분": "제외_목록", "업종명": f"({len(nm['제외_목록'])}개, {c.get('제외_참조')} 목록에서 복사)"})
                n += 1
        if not n:
            rows.append({"공고ID": pid, "공고명": title.get(pid, ""), "출처": src[pid], "위치": "", "제외_참조": "",
                         "구분": "", "업종명": "(업종 조건 없음)"})
    with open(S / "업종명_목록.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["공고ID", "공고명", "출처", "위치", "구분", "업종명", "제외_참조"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)}줄 → {S / '업종명_목록.csv'}")


if __name__ == "__main__":
    main()
