"""
셋 하나 채점

    cd eval
    python score.py 사용자추출_정답셋_전체148.csv       # 규칙만
    python score.py 사용자추출_정답셋_전체148.csv llm   # 규칙 + LLM (API 씀)

- 지역은 시도 · 시군구 · 후보_구만 비교 (원문 X)
- industry는 한쪽이 다른 쪽에 들어 있으면 맞음
- 다 맞은 문장 = 추출 12개 기준, 되묻기_유도는 따로
"""
import csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))     # user_extraction/
from extract_rules import extract_rules
from extract_llm import extract

HERE = Path(__file__).parent
SETS = HERE
RESULT = HERE
FIELDS = ["만나이", "거주지", "창업단계", "창업예정지", "사업장소재지", "업력_개월", "업종", "사업자_형태",
          "성별", "특수자격", "industry", "need", "되묻기_유도"]
CORE = FIELDS[:-1]      # 추출 12개 (되묻기_유도는 이걸로 계산한 거라 뺌)


def load(v):
    if v in ("", None):
        return None
    try:
        return json.loads(v)
    except ValueError:
        return v


def same(field, a, b):
    if field in ("거주지", "창업예정지", "사업장소재지"):
        key = lambda p: (p["시도"], p["시군구"], sorted(p["후보_구"] or []))
        return key(a) == key(b)
    if field in ("특수자격", "need", "되묻기_유도"):
        return sorted(a or []) == sorted(b or [])
    if field == "industry":
        if not a or not b:
            return a == b
        a, b = a.replace(" ", ""), b.replace(" ", "")
        return a in b or b in a
    if field in ("만나이", "업력_개월"):
        return (None if a is None else int(a)) == (None if b is None else int(b))
    return a == b


def score(set_name, run):
    """-> 필드별 맞은 수, 다 맞은 문장 수, 문장 수, 틀린 칸"""
    rows = list(csv.DictReader(open(SETS / set_name, encoding="utf-8-sig")))
    ok = {f: 0 for f in FIELDS}
    wrong, all_ok = [], 0
    for r in rows:
        got = run(r["입력문장"])
        miss = 0
        for f in FIELDS:
            gold = load(r[f])
            if same(f, got[f], gold):
                ok[f] += 1
            else:
                miss += f in CORE
                wrong.append({"ID": r["ID"], "유형": r["유형"], "필드": f, "정답": json.dumps(gold, ensure_ascii=False),
                              "추출": json.dumps(got[f], ensure_ascii=False), "입력문장": r["입력문장"]})
        all_ok += miss == 0
    return ok, all_ok, len(rows), wrong


def save_wrong(wrong, name):
    with open(RESULT / name, "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["ID", "유형", "필드", "정답", "추출", "입력문장"])
        w.writeheader(); w.writerows(wrong)


if __name__ == "__main__":
    SET = sys.argv[1] if len(sys.argv) > 1 else "사용자추출_정답셋_전체148.csv"
    RUN = extract if "llm" in sys.argv[2:] else extract_rules
    ok, all_ok, n, wrong = score(SET, RUN)
    print(f"[{'규칙 + LLM' if RUN is extract else '규칙만'}] {SET}")
    print(f"문장 {n}개, 추출 12개 필드 다 맞은 문장 {all_ok}개\n")
    for f in CORE:
        print(f"{f:8s} {ok[f]:2d}/{n} {ok[f] / n:6.1%}")
    print(f"\n[따로] 되묻기_유도 {ok['되묻기_유도']:2d}/{n} {ok['되묻기_유도'] / n:6.1%}")
    out = Path(SET).stem.replace("사용자추출_", "") + ("_llm" if RUN is extract else "_규칙만") + "_틀린칸.csv"
    save_wrong(wrong, out)
    print(f"\n틀린 칸 {len(wrong)}개 -> 04_채점결과/{out}")
