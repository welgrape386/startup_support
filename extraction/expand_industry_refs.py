"""추출 결과의 업종명에 표준 제외업종 목록(CSV)을 복사해 넣는다 (11/13, 팀 판정은 업종명만 씀)

사용법: python expand_industry_refs.py results/extract_v4_dev_terra [다른 결과 폴더 ...]
출력: <결과폴더>_업종확장/ (공고별 JSON + conditions_*.json). 원래 폴더는 그대로 둔다

업종 칸(최상위·트랙)마다
- 업종명.허용, 업종명.제외   : LLM이 원문에서 뽑은 것 (그대로 둠)
- 업종명.제외_목록           : 제외_참조가 가리키는 CSV 목록의 업종명 (코드가 채움)
- 업종명.제외_예외           : 그 목록에서 예외 문구가 있는 줄 "업종명: 예외 문구" (코드가 채움, 판정은 🔴 대신 ⚪ + 체크리스트)
- 제외_참조가 null·기타이거나 CSV에 없는 목록이면 제외_목록·제외_예외는 빈 목록 (기타는 체크리스트 "공고 별첨 제외업종 확인")
- 업종 코드도 대분류도 없는 포괄 문구("기타 … 장관이 지정한 업종")는 매칭할 수 없어 넣지 않는다
- 판정 쪽은 제외 + 제외_목록을 합쳐서 본다. 제외_참조 칸은 출처 추적용으로 그대로 남긴다
- 제외_참조가 있으면 업종명.제외에서 목록 별명("사치향락업종", "지원제한업종" 등, ALIAS)을 지우고 지운 말은 `제외_별명삭제`에 남긴다
- 업종 근거가 표준 목록을 가리키는 것 같은데 제외_참조가 null·기타인 칸은 `expand_review.csv`에 모은다 (사람이 확인 후 고침)
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "excluded/excluded_industries.csv"
# 표준 목록의 별명 (업종 이름이 아니라 목록을 부르는 말). 제외_참조가 있으면 업종명.제외에서 지운다 (11/13 결정)
ALIAS = re.compile(r"사치\s*향락|도박·투기·사치|제한\s*업종|제외\s*(대상\s*)?업종|융자\s*제외|보증\s*제한")
# 업종 근거가 표준 목록을 가리키는데 제외_참조가 null·기타이면 사람이 확인 (expand_review.csv)
REF_HINT = re.compile(r"보증\s*제한|지원\s*제한\s*업종|융자\s*제외|정책자금|사치\s*향락|별첨|붙임|참고\s*\d")


def load_lists():
    names, excs = defaultdict(list), defaultdict(list)
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not r["대분류"] and not r["KSIC코드"]:
                continue  # 포괄 문구
            names[r["참조명"]].append(r["업종명"])
            # "주) (운영형태)…"는 예외가 아니라 업종 설명 (기획부동산업)
            if r["예외"].strip() and not r["예외"].strip().startswith("주)"):
                excs[r["참조명"]].append(f"{r['업종명']}: {r['예외'].strip()}")
    return names, excs


def expand_cell(cell, names, excs, warn):
    nm = cell.setdefault("업종명", {"허용": [], "제외": []})
    nm.setdefault("허용", [])
    nm.setdefault("제외", [])
    ref = cell.get("제외_참조")
    if ref:
        # 별명, 그리고 LLM이 붙은 표준 목록 표를 옮긴 업종(CSV 목록과 같은 이름)은 제외에서 지운다 → 제외_목록으로 들어감
        listed = {re.sub(r"\s+", "", n) for n in names.get(ref, [])}
        drop = lambda w: ALIAS.search(w) or re.sub(r"\s+", "", w) in listed
        nm["제외_별명삭제"] = [w for w in nm["제외"] if drop(w)]
        nm["제외"] = list(dict.fromkeys(w for w in nm["제외"] if not drop(w)))
        if not nm["제외_별명삭제"]:
            del nm["제외_별명삭제"]
    if ref and ref != "기타" and ref not in names:
        warn.append(ref)
    nm["제외_목록"] = list(names.get(ref, [])) if ref else []
    # 공고에 직접 적힌 예외(예: 121291 "소매업: 단, 전자상거래 … 지원")는 남기고 CSV 예외를 뒤에 붙인다
    own = [e for e in nm.get("제외_예외") or [] if e not in excs.get(ref, [])]
    nm["제외_예외"] = own + (list(excs.get(ref, [])) if ref else [])


def main(dirs):
    names, excs = load_lists()
    for d in dirs:
        src = Path(d) if Path(d).is_absolute() else ROOT / d
        out = src.with_name(src.name + "_업종확장")
        out.mkdir(exist_ok=True)
        merged, warn, n_ref, review = [], [], 0, []
        for p in sorted(src.glob("PBLN_*.json")):
            j = json.loads(p.read_text(encoding="utf-8"))
            cells = [("최상위", j.get("업종"))] + [(t.get("이름"), (t.get("조건") or {}).get("업종"))
                                                for t in j.get("트랙") or []]
            for where, c in cells:
                if isinstance(c, dict):
                    if c.get("제외_참조") in (None, "기타") and REF_HINT.search(c.get("근거") or ""):
                        review.append({"공고ID": j["공고ID"], "위치": where, "제외_참조": c.get("제외_참조"),
                                       "근거": (c.get("근거") or "").replace("\n", " / ")})
                    expand_cell(c, names, excs, warn)
                    n_ref += bool(c["업종명"]["제외_목록"])
            (out / p.name).write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
            merged.append(j)
        name = f"conditions_{out.name.replace('extract_', '')}.json"
        (out / name).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        with open(out / "expand_review.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["공고ID", "위치", "제외_참조", "근거", "확인결과"])
            w.writeheader()
            w.writerows(review)
        print(f"{src.name}: {len(merged)}건 → {out.name}, 목록을 채운 업종 칸 {n_ref}개, 제외_참조 확인 필요 {len(review)}개"
              + (f", CSV에 없는 참조명: {sorted(set(warn))}" if warn else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
