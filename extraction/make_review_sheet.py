"""정답셋이 아닌 LLM 추출 공고의 판정용 칸을 사람이 훑어볼 검토표로 만든다 (11/13)

사용법: python make_review_sheet.py
입력: results/service_v4_업종확장/ (출처.csv에서 LLM 공고만)
출력: results/service_v4_검토표.csv — 한 줄 = 칸 하나 (최상위·트랙·대안조건 선택지 모두). '확인' 칸에 O/X, X면 '수정메모'에 적고 manual_fixes.json에 반영
- 판정에 쓰는 칸만: 신청자_유형, 사업자등록, 업력, 나이, 지역, 창업이력, 특수자격, 보유요건, 업종명 (기업규모는 체크리스트라 참고로만)
- 상태가 없음인 칸은 '없음인 칸' 줄 하나로 묶는다 (원문에 조건이 있는데 놓쳤는지 볼 때)
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "results/service_v4_업종확장"
OUT = ROOT / "results/service_v4_검토표.csv"
CELLS = ["신청자_유형", "사업자등록", "업력", "나이", "지역", "창업이력", "기업규모"]
LISTS = ["특수자격", "보유요건"]
TITLES = {r["공고ID"]: r["공고명"] for r in csv.DictReader(open(ROOT / "docs/target_seoul_national_62.csv", encoding="utf-8-sig"))}


def short(name, c):
    """칸 값 요약 (근거·null 뺌)"""
    if name == "업종":
        nm = c.get("업종명") or {}
        parts = []
        if nm.get("허용"):
            parts.append("허용: " + ", ".join(nm["허용"]))
        if nm.get("제외"):
            parts.append("제외: " + ", ".join(nm["제외"]))
        if c.get("제외_참조"):
            parts.append(f"제외_참조: {c['제외_참조']} (목록 {len(nm.get('제외_목록') or [])}개)")
        return " / ".join(parts)
    skip = {"상태", "근거"}
    return ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in c.items()
                     if k not in skip and v not in (None, [], {}, ""))


def rows_of(pid, cond, where, out):
    none = []
    for name in CELLS + ["업종"]:
        c = cond.get(name)
        if not isinstance(c, dict):
            continue
        st = c.get("상태")
        val = short(name, c)
        if st == "없음" and not (name == "업종" and val):
            none.append(name)
            continue
        out.append({"공고ID": pid, "공고명": TITLES.get(pid, ""), "위치": where,
                    "칸": "업종명" if name == "업종" else name + (" (체크리스트)" if name == "기업규모" else ""),
                    "상태": st, "값": val, "근거": (c.get("근거") or "").replace("\n", " ")})
    for name in LISTS:
        items = cond.get(name)
        items = items if isinstance(items, list) else ([items] if isinstance(items, dict) else [])
        for it in items:
            out.append({"공고ID": pid, "공고명": TITLES.get(pid, ""), "위치": where, "칸": name, "상태": "",
                        "값": short(name, it), "근거": (it.get("근거") or "").replace("\n", " ")})
    for i, alt in enumerate(cond.get("대안조건") or []):
        out.append({"공고ID": pid, "공고명": TITLES.get(pid, ""), "위치": where, "칸": f"대안조건[{i}]", "상태": "",
                    "값": alt.get("설명", ""), "근거": (alt.get("근거") or "").replace("\n", " ")})
        for j, opt in enumerate(alt.get("선택지") or []):
            rows_of(pid, opt, f"{where} 대안[{i}] 선택지{j + 1}", out)
    if none and "선택지" not in where:
        out.append({"공고ID": pid, "공고명": TITLES.get(pid, ""), "위치": where, "칸": "없음인 칸", "상태": "없음",
                    "값": ", ".join(none), "근거": ""})


def main():
    llm = [r["공고ID"] for r in csv.DictReader(open(SRC / "출처.csv", encoding="utf-8-sig")) if r["출처"].startswith("LLM")] \
        if (SRC / "출처.csv").exists() else None
    if llm is None:
        llm = [r["공고ID"] for r in csv.DictReader(open(ROOT / "results/service_v4/출처.csv", encoding="utf-8-sig"))
               if r["출처"].startswith("LLM")]
    out = []
    for pid in llm:
        j = json.loads((SRC / f"{pid}.json").read_text(encoding="utf-8"))
        rows_of(pid, j, "최상위", out)
        for t in j.get("트랙") or []:
            rows_of(pid, t.get("조건") or {}, f"트랙: {t.get('이름')}", out)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["공고ID", "공고명", "위치", "칸", "상태", "값", "근거", "확인", "수정메모"])
        w.writeheader()
        w.writerows(out)
    print(f"{len(llm)}건, {len(out)}줄 → {OUT}")


if __name__ == "__main__":
    main()
