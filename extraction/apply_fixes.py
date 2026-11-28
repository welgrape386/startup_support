"""추출 결과에 사람이 확인한 수정(results/manual_fixes.json)을 적용해 새 폴더에 저장한다 (원본은 그대로)

사용법: python apply_fixes.py results/extract_v4_all_terra
       python apply_fixes.py gold/extract_gold30 gold/gold_fixes.json   (11/19 정답셋 수정 → gold/extract_gold30_수정/)
출력: results/extract_v4_all_terra_수정/ (공고별 JSON + conditions_*.json + fixes_applied.csv)
그다음: python expand_industry_refs.py results/extract_v4_all_terra_수정  → _수정_업종확장/ (판정 입력)

manual_fixes.json: [{"공고ID", "경로", "값", "이유"}, ...]
- 경로: 점과 [번호]로 칸을 가리킨다. 예: "업종.제외_참조", "트랙[0].조건.업종.제외_참조", "제외대상[3].근거"
- "삭제": true 이면 그 칸(목록 원소)을 지운다 ("값"은 쓰지 않음). 같은 목록에서 여러 개를 지울 때는 뒤 번호부터 적는다
- 적용 전 값이 수정 목록의 "원래값"과 다르면(다시 추출해서 바뀐 경우) 적용하지 않고 알린다. "원래값"을 빼면 확인 없이 적용
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXES = ROOT / "results/manual_fixes.json"
_MISSING = object()


def steps(path):
    out = []
    for part in path.split("."):
        m = re.fullmatch(r"([^\[\]]+)((?:\[\d+\])*)", part)
        out.append(m.group(1))
        out += [int(i) for i in re.findall(r"\[(\d+)\]", m.group(2))]
    return out


def get_parent(obj, path):
    s = steps(path)
    for k in s[:-1]:
        obj = obj[k]
    return obj, s[-1]


def main(src, fixes_path=FIXES):
    src = Path(src) if Path(src).is_absolute() else ROOT / src
    out = src.with_name(src.name + "_수정")
    out.mkdir(exist_ok=True)
    fixes = json.loads(Path(fixes_path).read_text(encoding="utf-8"))
    by_id = {}
    for f in fixes:
        by_id.setdefault(f["공고ID"], []).append(f)
    log, merged = [], []
    for p in sorted(src.glob("PBLN_*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        for f in by_id.get(j["공고ID"], []):
            try:
                parent, key = get_parent(j, f["경로"])
                before = parent[key] if (isinstance(parent, list) or key in parent) else _MISSING
            except (KeyError, IndexError, TypeError):
                log.append({**f, "결과": "경로 없음"})
                continue
            if "원래값" in f and before != f["원래값"]:
                log.append({**f, "결과": f"원래값 다름: {before!r}"})
                continue
            if f.get("삭제"):
                del parent[key]
            else:
                parent[key] = f["값"]
            log.append({**f, "결과": "적용"})
        (out / p.name).write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
        merged.append(j)
    name = f"conditions_{out.name.replace('extract_', '')}.json"
    (out / name).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out / "fixes_applied.csv", "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["공고ID", "경로", "원래값", "값", "이유", "결과"], extrasaction="ignore")
        w.writeheader()
        for r in log:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items()})
    ok = sum(r["결과"] == "적용" for r in log)
    print(f"{src.name}: 수정 {len(log)}개 중 적용 {ok}개 → {out.name}")
    for r in log:
        if r["결과"] != "적용":
            print(f"  {r['공고ID']} {r['경로']}: {r['결과']}")


if __name__ == "__main__":
    # 두 번째 인자로 수정 목록을 바꿀 수 있다. 정답셋: python apply_fixes.py gold/extract_gold30 gold/gold_fixes.json
    main(sys.argv[1], *(ROOT / a for a in sys.argv[2:3]))
