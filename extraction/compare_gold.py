"""추출 결과를 추출 정답셋(gold/extract_gold30)과 비교한다

사용법: python compare_gold.py results/extract_v1_dev_luna [results/extract_v1_dev_sol ...]
       python compare_gold.py --gold gold/extract_gold30_수정_업종확장 results/extract_v4_eval_terra_업종확장   # 정답 폴더 지정
출력: 콘솔 요약 + <결과폴더>/compare_gold.csv (공고별), <결과폴더>/compare_gold_diff.txt (공고별로 빠진 것·더 뽑은 것)

비교 방법
- 공고 JSON을 "사실" 목록으로 펼친다. 예: (사업자등록, 있음, 필수), (업력, 있음, max=36, 이하), (제외대상, 국세지방세_체납)
- 최상위·트랙 조건·대안조건 선택지를 모두 펼쳐서 모은다 (어느 위치에 적었는지는 보지 않음)
  → 위치(트랙/대안조건) 구조는 따로 센다: 트랙 수, 트랙 이름, 대안조건 개수
- 근거 문장, 내용(자유 서술)은 비교하지 않는다 (근거는 verify_extraction.py 가 원문 대조)
- 정밀도 = 맞은 사실 / 뽑은 사실, 재현율 = 맞은 사실 / 정답 사실
- "판정 핵심" = 판정 결과를 바로 바꾸는 칸 (신청자_유형·사업자등록·업력·나이·지역·기업규모·창업이력)
- "업종명" = 업종 칸의 `업종명` 키워드 (11/12 추가). 전체 사실과 따로 센다 (v3 이전 점수와 비교할 수 있게).
  (허용/제외, 공백 뺀 키워드) 단위, 최상위·트랙 위치는 보지 않음. 정답에 업종명이 있는 공고만 센다
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLD = ROOT / "gold/extract_gold30"
CORE = {"신청자_유형", "사업자등록", "업력", "나이", "지역", "기업규모", "창업이력"}


def fs(x):
    return tuple(sorted(map(str, x))) if x else ()


def facts_of(name, d):
    """칸 하나(dict) → 사실 목록. 상태 없음·대안조건(값은 선택지에 있음)은 사실 없음"""
    st = d.get("상태")
    if st in (None, "없음", "대안조건"):
        return []
    if name == "신청자_유형":
        return [(name, st, v) for v in (d.get("값") or [None])]
    if name == "나이":
        return [(name, st, d.get("min"), d.get("경계_min"), d.get("max"), d.get("경계_max"), d.get("대상"))]
    if name == "성별":
        return [(name, st, d.get("값"), d.get("대상"))]
    if name == "지역":
        rng = fs((r.get("시도"), r.get("시군구")) for r in (d.get("범위") or []))
        return [(name, st, rng, fs(d.get("유형") or []), d.get("사후충족_허용"))]
    if name == "업력":
        cr = d.get("창업일_범위") or {}
        return [(name, st, d.get("min_개월"), d.get("max_개월"), d.get("경계_max"), cr.get("from"), cr.get("to"), d.get("단계"))]
    if name == "사업자등록":
        return [(name, st, d.get("값"))]
    if name == "창업이력":
        return [(name, st, d.get("사업자이력_허용"), d.get("폐업경과_min_개월"), d.get("동일업종_제한"))]
    if name == "업종":
        return [(name, st, d.get("제외_참조"), fs(c.get("코드") for c in (d.get("포함_대분류") or [])),
                 fs(c.get("코드") for c in (d.get("제외_대분류") or [])))]
    if name == "기업규모":
        return [(name, st, fs(d.get("구분") or []), d.get("상시근로자_max"), d.get("매출액_max_원"))]
    return []


def list_facts(name, items):
    if name == "보유요건":
        return [(name, i.get("종류")) for i in items]
    if name == "특수자격":
        return [(name, i.get("값")) for i in items]
    if name == "제외대상":
        return [(name, i.get("유형")) for i in items]
    if name == "기타조건":
        return [(name, i.get("구분")) for i in items]
    return []


def collect(cond, out, struct, where):
    """조건 묶음(최상위 또는 트랙 조건 또는 선택지) 하나를 펼친다
    형식이 틀린 부분(선택지·원소가 dict가 아니고 글자 등)은 건너뛴다 = 못 뽑은 것으로 셈
    (11/17 B1 최소 프롬프트 결과가 선택지를 글자로 적어서 추가. 형식을 지킨 결과의 점수는 바뀌지 않음)"""
    if not isinstance(cond, dict):
        return
    for k, v in cond.items():
        if isinstance(v, dict) and "상태" in v:
            out.extend(facts_of(k, v))
        elif k in ("보유요건", "특수자격", "제외대상", "기타조건"):
            items = v if isinstance(v, list) else [v]   # 대안조건 선택지 안에서는 원소 하나가 dict 로 옴
            out.extend(list_facts(k, [i for i in items if isinstance(i, dict)]))
        elif k == "대안조건" and isinstance(v, list):
            struct["대안조건"] += len(v)
            for alt in v:
                for opt in (alt.get("선택지") or [] if isinstance(alt, dict) else []):
                    collect(opt, out, struct, where + ".선택지")


def hashable(x):
    """사실 안의 값이 list·dict이면 비교할 수 있게 바꾼다 (형식이 틀린 결과용, 정상 결과는 그대로)"""
    if isinstance(x, (list, tuple)):
        return tuple(hashable(i) for i in x)
    if isinstance(x, dict):
        return json.dumps(x, ensure_ascii=False, sort_keys=True)
    return x


def flatten(j):
    out, struct = [], Counter()
    collect({k: v for k, v in j.items() if k not in ("공고ID", "스키마버전", "트랙")}, out, struct, "top")
    tracks = [t for t in j.get("트랙") or [] if isinstance(t, dict)]  # 형식이 틀린 트랙(글자)은 건너뜀
    for t in tracks:
        collect(t.get("조건") or {}, out, struct, "트랙")
    names = tuple(t.get("이름") for t in tracks)
    return Counter(hashable(f) for f in out), {"트랙수": len(names), "트랙이름": names, "대안조건": struct["대안조건"]}


def industry_names(j):
    """업종명 키워드 → Counter((허용/제외, 공백 뺀 키워드)). 업종명 칸이 하나도 없으면 None"""
    conds = [t.get("조건") for t in j.get("트랙") or [] if isinstance(t, dict)]
    cells = [j.get("업종")] + [c.get("업종") for c in conds if isinstance(c, dict)]
    cells = [c for c in cells if isinstance(c, dict) and isinstance(c.get("업종명"), dict)]
    if not cells:
        return None
    return Counter((side, re.sub(r"\s+", "", w)) for c in cells for side in ("허용", "제외")
                   for w in c["업종명"].get(side) or [])


def prf(g, p):
    hit = sum((g & p).values())
    P = hit / sum(p.values()) if p else 1.0
    R = hit / sum(g.values()) if g else 1.0
    return hit, P, R


def compare_dir(d):
    d = Path(d)
    rows, diffs = [], []
    tot = {"all": [0, 0, 0], "core": [0, 0, 0], "ind": [0, 0, 0]}
    ind_n = 0
    struct_ok = 0
    files = sorted(d.glob("PBLN_*.json"))
    for f in files:
        gp = GOLD / f.name
        if not gp.exists():
            continue
        gj, pj = json.loads(gp.read_text(encoding="utf-8")), json.loads(f.read_text(encoding="utf-8"))
        g, gs = flatten(gj)
        p, ps = flatten(pj)
        gi = industry_names(gj)
        if gi is not None:
            pi = industry_names(pj) or Counter()
            ind_n += 1
            tot["ind"][0] += sum((gi & pi).values())
            tot["ind"][1] += sum(gi.values())
            tot["ind"][2] += sum(pi.values())
            if gi != pi:
                diffs.append(f"===== {f.stem} 업종명")
                diffs += [f"  - 빠짐: {m}" for m in (gi - pi).elements()] + [f"  + 더 뽑음: {e}" for e in (pi - gi).elements()]
        gc = Counter({k: v for k, v in g.items() if k[0] in CORE})
        pc = Counter({k: v for k, v in p.items() if k[0] in CORE})
        hit, P, R = prf(g, p)
        chit, cP, cR = prf(gc, pc)
        for key, (h, gg, pp) in (("all", (hit, g, p)), ("core", (chit, gc, pc))):
            tot[key][0] += h
            tot[key][1] += sum(gg.values())
            tot[key][2] += sum(pp.values())
        same_struct = gs["트랙수"] == ps["트랙수"] and (gs["대안조건"] > 0) == (ps["대안조건"] > 0)
        struct_ok += same_struct
        rows.append({"공고ID": f.stem, "정밀도": f"{P:.2f}", "재현율": f"{R:.2f}", "핵심_정밀도": f"{cP:.2f}",
                     "핵심_재현율": f"{cR:.2f}", "정답_트랙수": gs["트랙수"], "추출_트랙수": ps["트랙수"],
                     "정답_대안조건": gs["대안조건"], "추출_대안조건": ps["대안조건"], "구조일치": same_struct})
        miss, extra = g - p, p - g
        diffs.append(f"===== {f.stem}  (트랙 정답 {gs['트랙이름']} / 추출 {ps['트랙이름']}, 대안조건 정답 {gs['대안조건']} / 추출 {ps['대안조건']})")
        diffs += [f"  - 빠짐: {m}" for m in miss.elements()] + [f"  + 더 뽑음: {e}" for e in extra.elements()]
    if not rows:
        print(f"{d}: 비교할 파일 없음")
        return
    with open(d / "compare_gold.csv", "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (d / "compare_gold_diff.txt").write_text("\n".join(diffs), encoding="utf-8")

    def pr(t):
        P = t[0] / t[2] if t[2] else 1
        R = t[0] / t[1] if t[1] else 1
        return f"정밀도 {P:.2f} / 재현율 {R:.2f} / F1 {2 * P * R / (P + R) if P + R else 0:.2f} (맞음 {t[0]}, 정답 {t[1]}, 추출 {t[2]})"
    print(f"\n### {d.name}  ({len(rows)}건)")
    print(f"  전체 사실 : {pr(tot['all'])}")
    print(f"  판정 핵심 : {pr(tot['core'])}")
    print(f"  구조(트랙 수·대안조건 유무) 일치: {struct_ok}/{len(rows)}")
    if ind_n:
        print(f"  업종명    : {pr(tot['ind'])}  ({ind_n}건)")
    print(f"  공고별: {d / 'compare_gold.csv'} / 차이: {d / 'compare_gold_diff.txt'}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--gold" in args:
        i = args.index("--gold")
        g = Path(args[i + 1])
        GOLD = g if g.is_absolute() else ROOT / g
        del args[i:i + 2]
    for arg in args:
        compare_dir(ROOT / arg if not Path(arg).is_absolute() else arg)
