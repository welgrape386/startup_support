"""
공고마다 업종 카테고리·나이 조건 붙이기 (조건 추출 JSON → 우리 카테고리 9개)

    python make_industry.py [조건 JSON 경로]

입력: 조건 추출 JSON (공고 목록, 업종.업종명 = 허용·제외·제외_목록·제외_예외), 업종_사전.csv
출력: industry_map.csv  공고ID·트랙 → 허용 카테고리("전체"면 제한 없음), 제외 카테고리,
                        제외_예외 카테고리 (제외인데 "단, ~은 가능" 예외 문구가 있음 → 판정 ❔, 검색은 안 씀)
                        트랙 빈칸 = 공고 전체 줄 (검색은 이 줄만), 트랙 있음 = 트랙별 줄 (판정용)
      age_map.csv       공고ID → 나이 min/max (대표자·본인·구성원 전원일 때만)
      *_check.csv       위 두 파일 + 확인용 칸 (위치, 원문 업종명, 나이 대상·근거)
      사전에 없는 업종명은 화면에 출력 → 업종_사전.csv에 추가

규칙
- 허용은 넓게, 제외는 확실한 것만 (사전 참고)
- 제외_예외에 단서가 있는 제외 업종("부동산업: 단, 부동산관리업은 가능")은 매칭 안 함
- 트랙 안 업종은 모든 트랙에 업종 조건이 있을 때만 공고 전체 조건으로 봄
  (허용은 트랙들의 합, 제외는 모든 트랙에 공통인 것만)
"""
import json, sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "00_참고자료" / "업종_v4" / "conditions_service_v4_업종확장.json"

notices = json.load(open(SRC, encoding="utf-8"))

book = pd.read_csv(HERE / "업종_사전.csv", encoding="utf-8-sig", dtype=str).fillna("").set_index("업종명")
unknown = set()


def cats(name, col):
    if name not in book.index:
        unknown.add(name)
        return set()
    return set(book.loc[name, col].split("|")) - {""}


def split_names(part):
    """업종 칸 → (허용, 제외, 예외 있는 제외). 제외_예외에 '업종명: 단, ~은 가능'이 있으면 예외 있는 제외로"""
    n = (part or {}).get("업종명") or {}
    allow = list(n.get("허용") or [])
    deny = list(dict.fromkeys(list(n.get("제외") or []) + list(n.get("제외_목록") or [])))
    hedged = {e.split(":")[0].strip() for e in n.get("제외_예외") or []}
    return allow, [x for x in deny if x not in hedged], [x for x in deny if x in hedged]


out, ages = [], []
for d in notices:
    allow, deny, hedge = split_names(d.get("업종"))
    where = "최상위"
    tracks = [((t.get("조건") or {}).get("업종")) for t in d.get("트랙") or []]
    if not (allow or deny or hedge) and tracks and all(t is not None for t in tracks) \
            and all(split_names(t) != ([], [], []) for t in tracks):
        per = [split_names(t) for t in tracks]
        allow = sorted(set().union(*(set(a) for a, _, _ in per))) if all(a for a, _, _ in per) else []
        deny = sorted(set.intersection(*(set(x) for _, x, _ in per)))
        hedge = sorted(set.intersection(*(set(h) for _, _, h in per)))
        where = "모든 트랙"
    allow_c = set().union(*(cats(x, "허용_카테고리") for x in allow)) if allow else set()
    deny_c = set().union(*(cats(x, "제외_카테고리") for x in deny)) if deny else set()
    hedge_c = set().union(*(cats(x, "제외_카테고리") for x in hedge)) if hedge else set()
    hedge_c -= deny_c                       # 확실한 제외가 있으면 그쪽이 우선
    out.append({"pblancId": d["공고ID"],
                "허용": "|".join(sorted(allow_c)) if allow else "전체",
                "제외": "|".join(sorted(deny_c)),
                "제외_예외": "|".join(sorted(hedge_c)),
                "위치": where if (allow or deny or hedge) else "",
                "허용_원문": " / ".join(allow),
                "제외_원문": " / ".join(deny[:15]) + (f" 외 {len(deny) - 15}개" if len(deny) > 15 else ""),
                "제외_예외_원문": " / ".join(hedge)})

    a = d.get("나이") or {}
    if a.get("상태") == "있음" and a.get("대상") in {"대표자", "신청자_본인", "구성원_전원"}:
        ages.append({"pblancId": d["공고ID"], "min": a.get("min"), "max": a.get("max"),
                     "대상": a.get("대상"), "근거": (a.get("근거") or "")[:60]})

# 트랙별 업종 (판정이 트랙마다 따로 판단할 때). 트랙 조건 = 공고 전체 조건 + 그 트랙 조건
#   허용: 트랙에 허용이 있으면 트랙 것, 없으면 공고 전체 것 / 제외: 공고 전체 + 트랙
def joined(names, col):
    return "|".join(sorted(set().union(*(cats(x, col) for x in names)))) if names else ""

track_rows = []
for d in notices:
    top_a, top_d, top_h = split_names(d.get("업종"))
    for t in d.get("트랙") or []:
        a, x, h = split_names((t.get("조건") or {}).get("업종"))
        allow = a or top_a
        deny = list(dict.fromkeys(top_d + x))
        hedge = [n for n in dict.fromkeys(top_h + h) if n not in deny]
        deny_c = joined(deny, "제외_카테고리")
        hedge_c = "|".join(sorted(set(joined(hedge, "제외_카테고리").split("|")) - set(deny_c.split("|")) - {""}))
        track_rows.append({"pblancId": d["공고ID"], "트랙": t.get("이름", ""),
                           "허용": joined(allow, "허용_카테고리") if allow else "전체",
                           "제외": deny_c, "제외_예외": hedge_c,
                           "허용_원문": " / ".join(allow), "제외_원문": " / ".join(deny[:15]) + (f" 외 {len(deny) - 15}개" if len(deny) > 15 else ""),
                           "제외_예외_원문": " / ".join(hedge)})

# 공고 전체 줄(트랙 빈칸) + 트랙 줄을 한 파일로. 검색은 트랙 빈칸 줄만, 판정은 둘 다
# 검색·판정이 읽는 파일은 필요한 칸만, 사람이 확인할 칸은 *_check.csv로
ind = pd.concat([pd.DataFrame(out).assign(트랙=""), pd.DataFrame(track_rows)], ignore_index=True)
ind["_순서"] = ind["트랙"].ne("")
ind = ind.sort_values(["pblancId", "_순서"], kind="stable").drop(columns="_순서")
cols = ["pblancId", "트랙", "허용", "제외", "제외_예외"]
ind[cols].to_csv(HERE / "industry_map.csv", index=False, encoding="utf-8-sig")
ind[cols + [c for c in ind.columns if c not in cols]].to_csv(HERE / "industry_map_check.csv", index=False, encoding="utf-8-sig")
age = pd.DataFrame(ages)
age[["pblancId", "min", "max"]].to_csv(HERE / "age_map.csv", index=False, encoding="utf-8-sig")
age.to_csv(HERE / "age_map_check.csv", index=False, encoding="utf-8-sig")
print(f"공고 {len(out)}건 → industry_map.csv / 나이 조건 {len(ages)}건 → age_map.csv")
print("허용 있음:", sum(o["허용"] != "전체" for o in out), "건 / 제외 카테고리 있음:", sum(bool(o["제외"]) for o in out), "건")
if unknown:
    print(f"\n사전에 없는 업종명 {len(unknown)}개 (업종_사전.csv에 추가):")
    for n in sorted(unknown): print("  ", n)
