"""안내정보 추출 결과 후처리 (11/17)

사용법: python postprocess_info.py results/info_v2_terra
출력: results/info_v2_terra_후처리/ (원본 폴더는 그대로 둠) + 거기서 verify_info.py 실행

하는 일
0. 금리·자부담 칸을 지운다 (11/17 정예은 결정, 안내정보에서 뺌)
1.모든 트랙에 똑같이 있는 목록 항목(지원내용·제출서류·우대사항)은 최상위로 올리고 트랙에서 지운다
   - 같은지 볼 때 근거는 빼고 비교 (v2에서 127032 제출서류 6개가 두 트랙에 반복됨)
   - 최상위에 이미 같은 항목이 있으면 트랙 쪽만 지운다
   - 그래서 비게 된 트랙 칸은 지운다 (트랙에는 최상위와 다른 것만 둔다)
2. 근거가 아닌 값의 줄바꿈을 지운다 ("표준 증명\n원" → "표준 증명원", 줄 끝에서 끊긴 단어라 붙임)
   모집일정에 시작·마감 날짜가 둘 다 있으면 `원문`은 지운다 (v3 120174)
   제출서류 필수 = "그 대상에 해당하면 꼭 내야 하나": 대상이 있는데 필수 false면 true로 (선택·가점·우대는 그대로)
3. 사람이 고친 것(results/info_manual_fixes.json)을 반영한다 (예: 127032 창업기획서 PPT)
4. API 값을 "API" 칸으로 붙인다 (data/bizinfo_all_*.csv, 민선님 announcements 표 이름)
   - 접수기간: 날짜면 apply_start/apply_end, "예산 소진시까지·상시 접수·선착순"이면 rolling=true,
     "세부사업별 상이"처럼 둘 다 아니면 셋 다 비우고 모집일정(원문)을 씀
   - support_types, region, seoul_gu는 나애님 매칭표 몫이라 여기서 안 붙임
"""
import copy
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIST_KEYS = ("지원내용", "제출서류", "우대사항")
ROLLING = re.compile(r"소진|상시|선착순|모집\s*마감")
PERIOD = re.compile(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")
EXEC_METHOD = {"직접수행", "기초자치단체", "광역자치단체"}


def key(x):
    return json.dumps({a: b for a, b in x.items() if a != "근거"}, ensure_ascii=False, sort_keys=True)


def lift_common(d, log):
    tr = d.get("트랙") or []
    for k in LIST_KEYS:
        top = d.get(k) or []
        top_keys = {key(x) for x in top}
        if len(tr) >= 2:
            common = set.intersection(*[{key(x) for x in t.get(k) or []} for t in tr])
            # 첫 트랙의 순서대로 올린다
            new = [x for x in tr[0].get(k) or [] if key(x) in common and key(x) not in top_keys]
            if new:
                d[k] = top + new
                top_keys |= common
                log.append(f"{k} {len(new)}개 최상위로 올림")
        for t in tr:
            if k in t:
                before = len(t[k] or [])
                t[k] = [x for x in t[k] or [] if key(x) not in top_keys]
                if len(t[k]) < before:
                    log.append(f"트랙 {t.get('이름')} {k} {before - len(t[k])}개 지움 (최상위와 같음)")
                if not t[k]:
                    del t[k]


def clean_newlines(v, path, log):
    """근거가 아닌 문자열 값의 줄바꿈 제거"""
    if isinstance(v, dict):
        for k, x in v.items():
            if k == "근거":
                continue
            if isinstance(x, str) and "\n" in x:
                v[k] = re.sub(r"\s*\n\s*", "", x)
                log.append(f"{path}.{k} 줄바꿈 지움")
            else:
                clean_newlines(x, f"{path}.{k}", log)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            clean_newlines(x, f"{path}[{i}]", log)


DROP = ("금리", "자부담")  # 11/17 정예은 결정: 안내정보에서 뺌 (프롬프트 v4는 뽑지만 여기서 지움)


def drop_fields(d):
    for b in [d] + [t for t in d.get("트랙") or [] if isinstance(t, dict)]:
        for k in DROP:
            b.pop(k, None)
    d["스키마버전"] = "안내-v0.3"  # 금리·자부담을 뺀 버전 (docs/안내정보_스키마.md)


def clean_rounds(b, where, log):
    """모집일정: 시작·마감이 둘 다 정확한 날짜면 원문은 지운다 (v3 120174)"""
    for x in b.get("모집일정") or []:
        if x.get("시작") and x.get("마감") and x.get("원문"):
            x["원문"] = None
            log.append(f"{where} 모집일정 {x.get('차수')} 원문 지움 (날짜 있음)")


# 필수 기준 (11/17 정예은): "이 서류가 없으면 신청이 안 되나?" 안 되면 필수, 신청은 되고 혜택만 못 받으면 선택
# → 가점·우대·자부담 면제 등 혜택을 받으려고 내는 서류는 선택
OPTIONAL = re.compile(r"선택|가점|가산점|우대|희망\s*시|희망자|면제|무료")


def fix_required(b, where, log):
    """필수 = '그 대상에 해당하면 꼭 내야 하나' (11/17 정예은 결정)
    대상(조건)이 있는데 필수 false면 true로. 단 '선택'·'가점'·'우대'·'희망 시'가 보이면 정말 선택이라 그대로 둔다
    (v3는 조건 붙은 서류를 true, v4는 false로 적어 실행마다 달랐음: 117022 필수 5 → 1)"""
    for x in b.get("제출서류") or []:
        txt = " ".join(str(x.get(k) or "") for k in ("서류명", "대상", "근거"))
        if x.get("대상") and x.get("필수") is False and not OPTIONAL.search(txt):
            x["필수"] = True
            log.append(f"{where} 제출서류 '{x.get('서류명')}' 필수로 (대상: {x.get('대상')})")


def apply_fixes(d, fixes, log):
    for f in fixes:
        if f["공고ID"] != d["공고ID"]:
            continue
        where = d if f["위치"] == "최상위" else next(t for t in d.get("트랙") or [] if t.get("이름") == f["위치"])
        if f["작업"] == "추가":
            if key(f["값"]) not in {key(x) for x in where.get(f["칸"]) or []}:
                where.setdefault(f["칸"], []).append(f["값"])
                log.append(f"수동 추가: {f['위치']} {f['칸']} {f['값']}")
        elif f["작업"] == "설정":  # 값 하나짜리 칸(최대지원금 등)을 통째로 바꿈
            if where.get(f["칸"]) != f["값"]:
                where[f["칸"]] = f["값"]
                log.append(f"수동 설정: {f['위치']} {f['칸']} {f['값']}")
        else:
            raise ValueError(f"모르는 작업: {f['작업']}")


def api_block(r):
    raw = r["reqstBeginEndDe"].strip()
    m = PERIOD.search(raw)
    files = [{"name": n, "url": u} for n, u in zip(r["fileNm"].split("@"), r["flpthNm"].split("@")) if n]
    exc = r["excInsttNm"].strip()
    return {
        "title": r["pblancNm"],
        "agency": r["jrsdInsttNm"],
        "operator": None if exc in EXEC_METHOD else exc or None,
        "execution_method": exc if exc in EXEC_METHOD else None,
        "target_name": r["trgetNm"],
        "summary": r["bsnsSumryCn"],
        "category_large": r["pldirSportRealmLclasCodeNm"],
        "category_medium": r["pldirSportRealmMlsfcCodeNm"],
        "apply_start": m.group(1) if m else None,
        "apply_end": m.group(2) if m else None,
        "rolling": bool(not m and ROLLING.search(raw)),
        "application_period_raw": raw,
        "application_method": r["reqstMthPapersCn"],
        "announcement_url": r["pblancUrl"],
        "application_url": r["rceptEngnHmpgUrl"] or None,
        "contact": r["refrncNm"],
        "attachment_files": files,
    }


def main():
    src = Path(sys.argv[1]) if Path(sys.argv[1]).is_absolute() else ROOT / sys.argv[1]
    out = src.with_name(src.name + "_후처리")
    out.mkdir(exist_ok=True)
    api = {}
    for f in sorted((ROOT / "data").glob("bizinfo_all_*.csv")):
        with open(f, encoding="utf-8-sig") as fh:
            api.update({r["pblancId"]: r for r in csv.DictReader(fh)})
    fx_path = ROOT / "results/info_manual_fixes.json"
    fixes = json.loads(fx_path.read_text(encoding="utf-8")) if fx_path.exists() else []
    merged, logs = {}, []
    for fp in sorted(src.glob("PBLN_*.json")):
        d = copy.deepcopy(json.loads(fp.read_text(encoding="utf-8")))
        log = []
        drop_fields(d)
        clean_newlines(d, "", log)
        for b, w in [(d, "최상위")] + [(t, f"트랙 {t.get('이름')}") for t in d.get("트랙") or []]:
            clean_rounds(b, w, log)
            fix_required(b, w, log)
        lift_common(d, log)
        apply_fixes(d, fixes, log)  # 공통 항목을 올린 뒤에 붙여야 목록 끝에 들어감
        d["API"] = api_block(api[d["공고ID"]]) if d["공고ID"] in api else None
        if d["API"] is None:
            log.append("API 값 없음")
        (out / fp.name).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        merged[d["공고ID"]] = d
        logs += [(d["공고ID"], x) for x in log]
    (out / f"info_{out.name}.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out / "postprocess_log.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["공고ID", "한 일"])
        w.writerows(logs)
    print(f"파일 {len(merged)}개 → {out}")
    for p in logs:
        print("  ", *p)
    subprocess.run([sys.executable, str(ROOT / "verify_info.py"), str(out)], check=True)


if __name__ == "__main__":
    main()
