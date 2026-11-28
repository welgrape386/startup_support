"""안내정보 추출 채점: LLM 결과(후처리 후) vs 정답 10건 (gold/info_gold10/info_라벨링.csv) (11/17)

사용법: python score_info.py [결과폴더=results/info_v4_terra_후처리]
출력: 콘솔 요약 + <결과폴더>/score_info.csv (항목별 맞음/틀림)

비교 단위 = "트랙별로 실제 적용되는 값" (최상위 + 그 트랙). 공통 항목을 최상위에 적었는지 트랙마다 적었는지는 보지 않음
- 트랙이 없는 공고는 최상위만. 정답·결과 중 한쪽에만 있는 트랙은 최상위 값으로 봄
- 한 값 칸
    · 지원규모: 공백·기호 뺀 글자가 같거나 한쪽이 다른 쪽을 포함하면 맞음 (없음끼리도 맞음)
    · 최대지원금: 만원 숫자가 같으면 맞음 (둘 다 없음도 맞음)
    · 중복지원: 상태(가능/불가/조건부/미확인)가 같으면 맞음
- 목록 칸 (정밀도·재현율): 제출서류(서류명), 우대사항(내용), 모집일정(차수·날짜)
    · 이름이 비슷하면(공백·기호 뺀 글자 기준 포함 관계 또는 유사도 0.6 이상) 같은 항목으로 짝지음
    · 우대사항은 이름이 달라도 같은 원문 문장을 근거로 댔으면 짝지음 (예: "1인 사업장" vs "홀로 사업을 운영하며…")
    · 제출서류는 짝지은 것 중 `필수`가 맞는 비율도 따로 셈
- 지원내용은 채점하지 않음 (요약이라 정답이 하나로 안 정해짐)
"""
import csv
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "gold/info_gold10/info_라벨링.csv"
NONE = {"없음", ""}


def norm(s):
    return re.sub(r"[\s·ㆍ‧,()\[\]「」『』'’‘\"“”.\-~/]", "", s or "")


def similar(a, b):
    """같은 항목인지: 포함 관계면 1, 아니면 유사도와 '짧은 쪽 글자가 긴 쪽에 얼마나 들어 있나' 중 큰 값
    (11/17: "만50세 이상 대표자" vs "신규 진출자 중 생년월일이 만50세 이상인 대표자"처럼 길게 풀어 쓴 경우를 짝짓기 위해 두 번째 값 추가)"""
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0
    if a in b or b in a:
        return 1
    sm = SequenceMatcher(None, a, b, autojunk=False)
    cover = sum(m.size for m in sm.get_matching_blocks() if m.size >= 2) / min(len(a), len(b))
    return max(sm.ratio(), cover - 0.1)  # 흩어진 한두 글자 우연 일치를 깎으려고 0.1 뺌


def load_gold():
    g = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # pid → 트랙("" = 최상위) → 칸 → rows
    for r in csv.DictReader(open(GOLD, encoding="utf-8-sig")):
        g[r["공고ID"]][r["트랙"]][r["칸"]].append(r)
    return g


def gold_single(rows, field):
    if not rows:
        return None
    r = rows[0]
    if field == "최대지원금":
        return None if r["값"] in NONE else float(r["값"])
    if field == "중복지원":
        return r["값"] or "미확인"
    return None if r["값"] in NONE else r["값"]


def gold_list(rows, field):
    out = []
    for r in rows:
        if field == "모집일정":
            if r["값"] == "없음":
                continue
            out.append({"이름": r["값"] or "", "시작": r["시작"] or None, "마감": r["마감"] or None, "원문": r["원문"] or None})
        else:
            if r["값"] in NONE:
                continue
            out.append({"이름": r["값"], "필수": {"O": True, "X": False}.get(r["필수"]), "근거": r.get("원문_문장") or ""})
    return out


def same_evidence(g, p):
    """정답의 원문 문장과 추출의 근거가 같은 원문 줄을 가리키는지 (짧은 쪽의 80% 이상이 겹침)"""
    a = norm((g or "").replace(" / ", ""))
    b = norm(p or "")
    if len(a) < 6 or len(b) < 6:
        return False
    sm = SequenceMatcher(None, a, b, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks() if m.size >= 3) / min(len(a), len(b)) >= 0.8


def pred_single(b, field):
    c = b.get(field)
    if field == "최대지원금":
        return None if not c or c.get("만원") is None else float(c["만원"])
    if field == "중복지원":
        return (c or {}).get("상태") or "미확인"
    return (c or {}).get("값") if c else None


def pred_list(b, field):
    out = []
    for x in b.get(field) or []:
        if field == "제출서류":
            out.append({"이름": x.get("서류명") or "", "필수": x.get("필수"), "근거": x.get("근거") or ""})
        elif field == "우대사항":
            out.append({"이름": x.get("내용") or "", "근거": x.get("근거") or ""})
        else:
            out.append({"이름": x.get("차수") or "", "시작": x.get("시작"), "마감": x.get("마감"), "원문": x.get("원문")})
    return out


def match(gl, pl, field):
    """탐욕 짝짓기: 유사도 높은 순. 모집일정은 날짜·원문까지 같아야 짝"""
    pairs, used_g, used_p = [], set(), set()
    cand = []
    for i, g in enumerate(gl):
        for j, p in enumerate(pl):
            if field == "모집일정":
                same_date = (g["시작"], g["마감"]) == (p["시작"], p["마감"])
                s = 1 if same_date and (not g["원문"] or norm(g["원문"]) in norm(p["원문"] or "") or not g["이름"] or similar(g["이름"], p["이름"]) >= 0.6) else 0
            else:
                s = similar(g["이름"], p["이름"])
                # 이름이 달라도 같은 원문 문장을 근거로 댔으면 같은 항목 (우대사항만: 서류는 한 줄에 여러 개가 있어 잘못 짝지을 수 있음)
                if s < 0.6 and field == "우대사항" and same_evidence(g.get("근거"), p.get("근거")):
                    s = 0.6
            if s >= 0.6:
                cand.append((s, i, j))
    for s, i, j in sorted(cand, reverse=True):
        if i not in used_g and j not in used_p:
            used_g.add(i)
            used_p.add(j)
            pairs.append((i, j))
    return pairs


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results/info_v4_terra_후처리"
    gold = load_gold()
    single = {f: [0, 0] for f in ("지원규모", "최대지원금", "중복지원")}
    lists = {f: [0, 0, 0] for f in ("제출서류", "우대사항", "모집일정")}  # 맞음, 정답 수, 추출 수
    req = [0, 0]
    rows = []
    for pid, gtracks in sorted(gold.items()):
        pj = json.loads((out_dir / f"{pid}.json").read_text(encoding="utf-8"))
        ptracks = {t.get("이름"): t for t in pj.get("트랙") or []}
        names = sorted({n for n in gtracks if n} | set(ptracks)) or [""]
        for tn in names:
            gt, gtop = gtracks.get(tn, {}), gtracks.get("", {})
            pt = ptracks.get(tn, {}) if tn else {}
            where = tn or "최상위"
            for f in single:
                gv = gold_single(gt.get(f) or gtop.get(f) or [], f)
                pv = pred_single(pt, f) if pt.get(f) is not None else pred_single(pj, f)
                if f == "지원규모":
                    ok = (gv is None and pv is None) or (gv is not None and pv is not None and similar(gv, pv) == 1)
                else:
                    ok = gv == pv
                single[f][0] += ok
                single[f][1] += 1
                rows.append({"공고ID": pid, "위치": where, "칸": f, "정답": gv, "추출": pv, "결과": "맞음" if ok else "틀림"})
            for f in lists:
                gl = gold_list((gt.get(f) or []) + (gtop.get(f) or []) if tn else gtop.get(f) or [], f)
                pl = pred_list(pj, f) + (pred_list(pt, f) if pt else [])
                pairs = match(gl, pl, f)
                lists[f][0] += len(pairs)
                lists[f][1] += len(gl)
                lists[f][2] += len(pl)
                pg = {i for i, _ in pairs}
                pp = {j for _, j in pairs}
                for i, j in pairs:
                    extra = ""
                    if f == "제출서류" and gl[i]["필수"] is not None:
                        req[1] += 1
                        same = gl[i]["필수"] == pl[j]["필수"]
                        req[0] += same
                        extra = "" if same else f" (필수 다름: 정답 {gl[i]['필수']}, 추출 {pl[j]['필수']})"
                    rows.append({"공고ID": pid, "위치": where, "칸": f, "정답": gl[i]["이름"], "추출": pl[j]["이름"], "결과": "맞음" + extra})
                rows += [{"공고ID": pid, "위치": where, "칸": f, "정답": gl[i]["이름"], "추출": "", "결과": "빠짐"}
                         for i in range(len(gl)) if i not in pg]
                rows += [{"공고ID": pid, "위치": where, "칸": f, "정답": "", "추출": pl[j]["이름"], "결과": "더 뽑음"}
                         for j in range(len(pl)) if j not in pp]
    with open(out_dir / "score_info.csv", "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["공고ID", "위치", "칸", "정답", "추출", "결과"])
        w.writeheader()
        w.writerows(rows)
    print(f"### {out_dir.name} vs 정답 {len(gold)}건 (트랙별 적용 값 기준)")
    for f, (ok, n) in single.items():
        print(f"  {f:6}: 정확도 {ok / n:.2f} ({ok}/{n})")
    for f, (h, g, p) in lists.items():
        P = h / p if p else 1
        R = h / g if g else 1
        print(f"  {f:6}: 정밀도 {P:.2f} / 재현율 {R:.2f} / F1 {2 * P * R / (P + R) if P + R else 0:.2f} (맞음 {h}, 정답 {g}, 추출 {p})")
    print(f"  제출서류 필수 일치: {req[0]}/{req[1]}")
    print(f"  항목별: {out_dir / 'score_info.csv'}")


if __name__ == "__main__":
    main()
