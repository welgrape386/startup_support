"""근거 일치율: 결과 JSON 안의 모든 `근거` 문장이 원문에 그대로 있는지 (공백 무시) — 형식이 틀린 결과에도 쓸 수 있게 (11/17)

verify_extraction.py와 같은 비교(공백을 지운 뒤 포함 여부)지만, 스키마 검사 없이 근거만 센다
사용법: python evidence_rate.py results/extract_b1_minimal_eval_terra [results/...]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def evidences(x):
    if isinstance(x, dict):
        for k, v in x.items():
            if k == "근거" and isinstance(v, str) and v.strip():
                yield v
            else:
                yield from evidences(v)
    elif isinstance(x, list):
        for v in x:
            yield from evidences(v)


def main():
    for arg in sys.argv[1:]:
        d = Path(arg) if Path(arg).is_absolute() else ROOT / arg
        tot = ok = n = 0
        for f in sorted(d.glob("PBLN_*.json")):
            text = re.sub(r"\s+", "", (ROOT / "output/texts" / f"{f.stem}.txt").read_text(encoding="utf-8"))
            for e in evidences(json.loads(f.read_text(encoding="utf-8"))):
                tot += 1
                ok += re.sub(r"\s+", "", e) in text
            n += 1
        print(f"{d.name}: 파일 {n}개, 근거 {tot}개 중 원문에 있음 {ok}개 ({ok / tot:.1%})" if tot else f"{d.name}: 근거 없음")


if __name__ == "__main__":
    main()
