"""안내정보 추출 결과 검사 + 검토표 (11/16, prompts/info_v*.md 결과용)

사용법: python verify_info.py results/info_v1_terra
출력 (결과 폴더 안)
- info_check.csv : 문제 목록 (칸 누락, 허용값 아님, 근거를 원문에서 못 찾음, 숫자가 근거에 없음, 트랙 이름이 자격 추출과 다름)
- info_검토표.csv : 항목 하나에 한 줄 (공고ID, 공고명, 위치, 칸, 번호, 값, 근거, 문제) → 사람이 훑어봄

숫자 검사 (LLM이 숫자를 잘못 옮기는 실수 잡기)
- 최대지원금: `원문` 문구가 근거 안에 있는지 (만원 값은 원문 표현에서 바꾼 것이라 직접 비교 못 함)
- 우대 가점: 그 숫자가 근거 안에 있는지 (자부담 비율 검사는 11/17 자부담 칸을 빼면서 지움)
- 모집일정 날짜: 월·일 숫자가 근거 안에 있는지
- 지원내용 `내용`: 안에 있는 숫자가 모두 근거 안에 있는지
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# 11/17 정예은 결정: 금리·자부담은 안내정보에서 뺌 (추출은 v4 그대로, postprocess_info.py가 지움)
TOP = ["공고ID", "스키마버전", "지원규모", "최대지원금", "중복지원", "지원내용", "제출서류", "우대사항", "모집일정", "트랙"]
ENUM = {("중복지원", "상태"): {"가능", "불가", "조건부", "미확인"}}
TRACK_KEYS = set(TOP[2:9])
DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")


def squash(s):
    return re.sub(r"\s+", "", s or "")


def nums(s):
    """문자열 안의 숫자들 (쉼표 뺌): '1,900만원 5회' → ['1900', '5']"""
    return [n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", s or "")]


UNIT = {"억": 10000, "천만": 1000, "백만": 100, "만": 1, "천": 0.1, "": 0.0001}


def amounts_manwon(s):
    """'20~30억원', '1,900만원', '3,500천원', '13,600,000원' → 만원 값 목록 (v3 124232 '30억' → 30000 오류를 못 잡아 추가)"""
    out = []
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(?:~\s*(\d[\d,]*(?:\.\d+)?)\s*)?(억|천만|백만|만|천)?\s*원", s or ""):
        for g in (m.group(1), m.group(2)):
            if g:
                out.append(round(float(g.replace(",", "")) * UNIT[m.group(3) or ""], 1))
    return out


def iter_values(d):
    """근거가 아닌 문자열 값 (트랙 안은 빼고): (칸, 값)"""
    for k, v in d.items():
        if k in ("트랙", "근거", "API"):  # API 값은 원본 그대로 (줄바꿈 있어도 됨)
            continue
        items = v if isinstance(v, list) else [v]
        for x in items:
            if isinstance(x, dict):
                yield from ((k, s) for kk, s in x.items() if kk != "근거" and isinstance(s, str))


def check_block(d, where, text, rows, probs):
    """최상위 또는 트랙 하나를 검사하고 검토표 줄을 만든다"""
    def ev_ok(ev):
        return bool(ev) and squash(ev) in text

    def add(field, i, value, ev, extra=None):
        p = []
        if ev and not ev_ok(ev):
            p.append("근거를 원문에서 못 찾음")
        if extra:
            p.append(extra)
        rows.append({"위치": where, "칸": field, "번호": i, "값": value, "근거": (ev or "").replace("\n", " / "),
                     "문제": "; ".join(p)})
        probs.extend((where, field, i, x) for x in p)

    def num_in(n, ev):
        return n is None or str(n).rstrip("0").rstrip(".") in squash(ev).replace(",", "")

    for (f, k), allowed in ENUM.items():
        c = d.get(f)
        if isinstance(c, dict) and c.get(k) not in allowed:
            probs.append((where, f, "", f"{k} 허용값 아님: {c.get(k)!r}"))
    if (c := d.get("지원규모")):
        # 표에서 숫자만 옮기면 단위(억원·개사)가 빠짐 (v2 126965 "36,820" — 표 머리의 단위는 억원)
        add("지원규모", "", c.get("값"), c.get("근거"),
            "단위 없음 (숫자만)" if re.fullmatch(r"[\d,.\s]+", c.get("값") or "x") else None)
    for f, v in iter_values(d):
        if "\n" in v:
            probs.append((where, f, "", "값에 줄바꿈"))
    if (c := d.get("최대지원금")):
        # 표에서 "구분 + 금액"으로 줄여 쓸 수 있으므로 문구 전체가 아니라 숫자만 근거에 있는지 본다 (v2)
        bad = [x for x in nums(c.get("원문")) if x not in squash(c.get("근거")).replace(",", "")]
        miss = f"원문 숫자가 근거에 없음 {bad}" if bad else None
        if c.get("원문") and (len(c["원문"]) > 30 or "\n" in c["원문"]):
            miss = "원문이 너무 김 (30자 넘음 또는 줄바꿈)"
        am = amounts_manwon(c.get("원문"))
        if am and c.get("만원") is not None and float(c["만원"]) != max(am):
            miss = f"만원 값이 원문 금액과 다름 (원문 최대 {max(am):g}만원)"
        add("최대지원금", "", f"{c.get('만원')}만원 ({c.get('기준')}) {c.get('원문')}", c.get("근거"), miss)
    if (c := d.get("중복지원")) and c.get("상태") != "미확인":
        add("중복지원", "", f"{c.get('상태')}: {c.get('내용')}", c.get("근거"))
    for i, x in enumerate(d.get("지원내용") or [], 1):
        bad = [n for n in nums(x.get("내용")) if n not in squash(x.get("근거")).replace(",", "")]
        add("지원내용", i, f"{x.get('항목')}: {x.get('내용')}", x.get("근거"), f"근거에 없는 숫자 {bad}" if bad else None)
    for i, x in enumerate(d.get("제출서류") or [], 1):
        add("제출서류", i, f"{x.get('서류명')} ({'필수' if x.get('필수') else '선택' if x.get('필수') is False else '?'})"
            + (f" [{x['대상']}]" if x.get("대상") else ""), x.get("근거"))
    for i, x in enumerate(d.get("우대사항") or [], 1):
        add("우대사항", i, f"{x.get('내용')} (+{x.get('가점')})", x.get("근거"),
            None if num_in(x.get("가점"), x.get("근거") or "") else "가점이 근거에 없음")
    for i, x in enumerate(d.get("모집일정") or [], 1):
        bad = []
        for k in ("시작", "마감"):
            v = x.get(k)
            if v and not DATE.match(v):
                bad.append(f"{k} 날짜 형식")
            elif v:
                m, dd = int(v[5:7]), int(v[8:10])
                e = squash(x.get("근거"))
                if not re.search(rf"(?<!\d)0?{m}(?!\d)", e) or not re.search(rf"(?<!\d)0?{dd}(?!\d)", e):
                    bad.append(f"{k} 날짜가 근거에 없음")
        if not (x.get("시작") or x.get("마감") or x.get("원문")):
            bad.append("날짜·원문 둘 다 없음")  # v2 124232 "1차" 빈 줄
        add("모집일정", i, f"{x.get('차수')}: {x.get('시작')} ~ {x.get('마감')}"
            + (f" ({x['원문']})" if x.get("원문") else ""), x.get("근거"), "; ".join(bad) or None)


def main():
    out = Path(sys.argv[1]) if Path(sys.argv[1]).is_absolute() else ROOT / sys.argv[1]
    titles = {r["공고ID"]: r["공고명"] for r in csv.DictReader(open(ROOT / "docs/target_seoul_national_62.csv", encoding="utf-8-sig"))}
    rows_all, probs_all, n = [], [], 0
    for fp in sorted(out.glob("PBLN_*.json")):
        pid, n = fp.stem, n + 1
        d = json.loads(fp.read_text(encoding="utf-8"))
        text = squash((ROOT / "output/texts" / f"{pid}.txt").read_text(encoding="utf-8"))
        probs = [("최상위", k, "", "칸 누락") for k in TOP if k not in d]
        probs += [("최상위", k, "", "스키마에 없는 칸") for k in d if k not in TOP and k != "API"]
        rows = []
        check_block(d, "최상위", text, rows, probs)
        cond = ROOT / "results/service_v4_업종확장" / fp.name
        names = [t["이름"] for t in json.loads(cond.read_text(encoding="utf-8")).get("트랙") or []] if cond.exists() else []
        # 모든 트랙에 똑같이 있는 목록 항목은 최상위에 한 번만 있어야 함 (v2에서 127032 제출서류가 트랙마다 반복됨)
        tr = d.get("트랙") or []
        if len(tr) >= 2:
            for k in ("지원내용", "제출서류", "우대사항"):
                key = lambda x: json.dumps({a: b for a, b in x.items() if a != "근거"}, ensure_ascii=False, sort_keys=True)
                common = set.intersection(*[{key(x) for x in t.get(k) or []} for t in tr])
                if common:
                    probs.append(("트랙 전체", k, "", f"모든 트랙에 같은 항목 {len(common)}개 (최상위로 옮겨야 함)"))
        for t in d.get("트랙") or []:
            w = f"트랙: {t.get('이름')}"
            if t.get("이름") not in names:
                probs.append((w, "트랙", "", "자격 추출에 없는 트랙 이름"))
            probs += [(w, k, "", "트랙에 올 수 없는 칸") for k in t if k != "이름" and k not in TRACK_KEYS]
            check_block(t, w, text, rows, probs)
        if not rows:
            rows.append({"위치": "", "칸": "", "번호": "", "값": "(뽑은 항목 없음)", "근거": "", "문제": ""})
        rows_all += [{"공고ID": pid, "공고명": titles.get(pid, ""), **r} for r in rows]
        probs_all += [(pid, *p) for p in probs]
    with open(out / "info_검토표.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["공고ID", "공고명", "위치", "칸", "번호", "값", "근거", "문제"])
        w.writeheader()
        w.writerows(rows_all)
    with open(out / "info_check.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["공고ID", "위치", "칸", "번호", "문제"])
        w.writerows(probs_all)
    print(f"파일 {n}개, 검토표 {len(rows_all)}줄, 문제 {len(probs_all)}개 → {out / 'info_check.csv'}")
    for p in probs_all[:30]:
        print("  ", *p)


if __name__ == "__main__":
    main()
