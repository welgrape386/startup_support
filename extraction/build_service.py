"""서비스 데이터(판정 입력)를 만든다: 정답셋 30건은 정답 JSON, 나머지는 LLM 추출 + 사람 수정 (11/13)

사용법: python build_service.py
입력: results/extract_v4_all_terra_수정/ (apply_fixes.py 결과), gold/extract_gold30/
출력: results/service_v4/ (62건 + conditions_service_v4.json + 출처.csv)
그다음: python expand_industry_refs.py results/service_v4 → results/service_v4_업종확장/ (주희님께 드릴 판정 입력)

- 추출 성능 평가에는 이 폴더를 쓰지 않는다 (정답 30건이 들어 있어 점수가 부풀려짐). 평가는 results/extract_v4_*_terra 원본으로
- 정답셋 업종명은 정예은 검수 전 (gold/README.md 11/12)
"""
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LLM = ROOT / "results/extract_v4_all_terra_수정"
GOLD = ROOT / "gold/extract_gold30_수정"  # 11/19 정답셋 원본에 gold/gold_fixes.json 적용한 것 (apply_fixes.py)
IDS = ROOT / "prompts/target_ids_seoul_national_62.txt"  # 11/13 64건에서 122497·127096 제외 (docs/target_excluded_from_64.csv)
OUT = ROOT / "results/service_v4"


def main():
    OUT.mkdir(exist_ok=True)
    ids = [l.strip() for l in IDS.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows, merged = [], []
    for pid in ids:
        g = GOLD / f"{pid}.json"
        src, how = (g, "정답셋 (사람 검수)") if g.exists() else (LLM / f"{pid}.json", "LLM v4 추출 + 수정 (manual_fixes.json)")
        shutil.copyfile(src, OUT / f"{pid}.json")
        merged.append(json.loads(src.read_text(encoding="utf-8")))
        rows.append({"공고ID": pid, "출처": how})
    (OUT / "conditions_service_v4.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(OUT / "출처.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["공고ID", "출처"])
        w.writeheader()
        w.writerows(rows)
    n = sum(r["출처"].startswith("정답셋") for r in rows)
    print(f"{len(rows)}건 → {OUT.name} (정답셋 {n}, LLM {len(rows) - n})")


if __name__ == "__main__":
    main()
