"""추출 결과 JSON 검증: 파싱, 칸·하위 필드 누락, 허용값, 근거 원문 대조 (스키마 v0.6, 1-2절)

사용법: python verify_extraction.py <결과폴더> [텍스트폴더=output/texts]
출력: <결과폴더>/evidence_check.csv, <결과폴더>/schema_check.csv, 콘솔 요약
"""
import csv
import json
import re
import sys
from pathlib import Path

FIELDS = {
    "신청자_유형": ["상태", "값", "근거"],
    "나이": ["상태", "min", "max", "경계_min", "경계_max", "나이_기준", "기준일", "출생일_범위", "대상", "근거"],
    "성별": ["상태", "값", "대상", "근거"],
    "지역": ["상태", "범위", "유형", "유형_결합", "기준일", "사후충족_허용", "사후충족_기한", "근거"],
    "업력": ["상태", "업력_기준", "min_개월", "max_개월", "경계_min", "경계_max", "기준일", "단계", "창업일_범위", "근거"],
    "사업자등록": ["상태", "값", "기준일", "근거"],
    "창업이력": ["상태", "사업자이력_허용", "폐업경과_min_개월", "동일업종_제한", "기준일", "예외", "근거"],
    "업종": ["상태", "포함", "제외", "포함_대분류", "제외_대분류", "KSIC코드", "제외_참조", "근거"],
    "기업규모": ["상태", "구분", "상시근로자_max", "매출액_max_원", "근거"],
}
# 선택 칸 (없어도 누락 아님, 상태 없음이어도 채울 수 있음). 업종명: 원문 업종 키워드 {"허용": [...], "제외": [...]} (11/11 추가, 카테고리 매칭용)
OPTIONAL = {"업종": ["업종명"]}
LISTS = ["보유요건", "특수자격", "제외대상", "대안조건", "기타조건", "트랙"]
TOP_KEYS = ["공고ID", "스키마버전"] + list(FIELDS) + LISTS

D4 = ["공고일", "접수마감일", "협약일", "명시없음"]
SIDO = ["서울특별시", "부산광역시", "대구광역시", "인천광역시", "대전광역시", "울산광역시", "세종특별자치시", "경기도",
        "강원특별자치도", "충청북도", "충청남도", "전북특별자치도", "경상북도", "경상남도", "제주특별자치도", "전남광주통합특별시"]
ENUMS = {
    "상태": ["있음", "없음", "불명확", "대안조건"],
    "신청자_유형.값": ["예비창업자", "개인사업자", "법인", "대학생", "기관·단체", "기타"],
    "나이.경계_min": ["이상", "초과"], "나이.경계_max": ["이하", "미만"],
    "나이.나이_기준": ["만나이", "연나이", "보험나이", "명시없음"],
    "나이.기준일": D4,
    "나이.대상": ["대표자", "공동대표_전원", "신청자_본인", "구성원_전원", "채용대상"],
    "성별.값": ["여성", "남성"],
    "성별.대상": ["대표자", "공동대표_전원", "신청자_본인", "구성원_전원", "채용대상"],
    "지역.유형": ["본사소재지", "공장소재지", "사업장소재지", "사업자등록지", "거주지", "주민등록지", "명시없음"],
    "지역.유형_결합": ["하나만", "모두"],
    "지역.기준일": D4,
    "지역.사후충족_기한": ["협약일", "선정후", "사업기간내", "명시없음"],
    "업력.업력_기준": ["사업자등록일", "법인설립등기일", "개업일", "명시없음"],
    "업력.경계_min": ["이상", "초과"], "업력.경계_max": ["이하", "미만"],
    "업력.기준일": D4,
    "업력.단계": ["초기", "도약", "기타"],
    "사업자등록.값": ["필수", "불가", "무관", "사후등록"],
    "사업자등록.기준일": D4,
    "창업이력.사업자이력_허용": ["불가", "폐업후허용", "무관"],
    "창업이력.기준일": ["공고일", "접수마감일", "명시없음"],
    "업종.제외_참조": ["소상공인정책자금_융자제외", "신용보증재단_보증제한", "창업지원법_제외", "중소기업정책자금_융자제외", "기타"],
    "기업규모.구분": ["소상공인", "소기업", "중소기업", "중견기업"],
    "보유요건.종류": ["소상공인확인서", "중소기업확인서", "통신판매업신고증", "벤처기업확인", "이노비즈", "메인비즈",
                   "기업부설연구소", "지식재산권", "수출실적", "매출실적", "기타"],
    "특수자격.값": ["청년", "여성", "장애인", "재창업자", "경력단절여성", "북한이탈주민", "다문화가족", "국가유공자", "대학생", "기타"],
    "제외대상.유형": ["휴폐업", "국세지방세_체납", "금융_연체·신용불량", "자본잠식", "중복수혜", "참여제한", "업종제외",
                  "프랜차이즈", "취급불가품목", "허위신청", "기관재량", "기타"],
    "제외대상.적용대상": ["신청자", "대표자", "법인", "총괄책임자", "제품"],
    "제외대상.기준일": ["접수마감일", "최초신청일", "공고일", "협약일", "명시없음"],
    "기타조건.구분": ["사업분야", "자부담", "채용", "기타"],
}
KSIC = set("ABCDEFGHIJKLMNOPQRSTU")


def normalize(text):
    """공백 제거한 문자열과, 그 각 글자의 원문 위치"""
    chars, pos = [], []
    for i, c in enumerate(text):
        if not c.isspace():
            chars.append(c)
            pos.append(i)
    return "".join(chars), pos


DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")


def check_enum(key, value, path, problems):
    allowed = ENUMS.get(key)
    if allowed is None or value is None:
        return
    for v in value if isinstance(value, list) else [value]:
        # 기준일은 허용값 대신 날짜도 가능 (v0.6)
        if key.endswith(".기준일") and isinstance(v, str) and DATE.match(v):
            continue
        if v not in allowed:
            problems.append((path, f"허용값 아님: {v!r}"))


def check_cell(name, cell, path, problems, full):
    """칸 하나 검사. full=False면 (대안조건 선택지·트랙 조건 안) 하위 필드 누락은 보지 않는다"""
    if not isinstance(cell, dict):
        problems.append((path, "객체가 아님"))
        return
    if full:
        for f in FIELDS[name]:
            if f not in cell:
                problems.append((path, f"필드 누락: {f}"))
    for f in cell:
        if f not in FIELDS[name] and f not in OPTIONAL.get(name, []):
            problems.append((path, f"스키마에 없는 필드: {f}"))
    check_enum("상태", cell.get("상태"), f"{path}.상태", problems)
    for f, v in cell.items():
        check_enum(f"{name}.{f}", v, f"{path}.{f}", problems)
    if cell.get("상태") in ("없음", "대안조건"):
        filled = [f for f, v in cell.items() if f != "상태" and f not in OPTIONAL.get(name, []) and v not in (None, [])]
        if filled:
            problems.append((path, f"상태 {cell['상태']}인데 값이 있음: {filled}"))
    if cell.get("상태") in ("있음", "불명확") and not cell.get("근거"):
        problems.append((path, "근거 없음"))
    if name == "지역":
        for r in cell.get("범위") or []:
            if r.get("시도") not in SIDO:
                problems.append((path, f"시도 허용값 아님: {r.get('시도')!r}"))
        types = cell.get("유형") or []
        if len(types) >= 2 and cell.get("유형_결합") is None:
            problems.append((path, "유형 2개 이상인데 유형_결합 없음"))
    if name == "업종":
        for k in ("포함_대분류", "제외_대분류"):
            for d in cell.get(k) or []:
                if d.get("코드") not in KSIC:
                    problems.append((path, f"KSIC 대분류 아님: {d.get('코드')!r}"))


def check_list(name, items, path, problems):
    if not isinstance(items, list):
        problems.append((path, "목록이 아님"))
        return
    for i, it in enumerate(items):
        p = f"{path}[{i}]"
        for f, v in it.items():
            check_enum(f"{name}.{f}", v, f"{p}.{f}", problems)
        if name == "제외대상":
            if (it.get("유형") == "프랜차이즈") != (it.get("프랜차이즈") is not None):
                problems.append((p, "유형과 프랜차이즈 필드가 맞지 않음"))
        if name == "대안조건":
            for j, opt in enumerate(it.get("선택지") or []):
                check_conditions(opt, f"{p}.선택지[{j}]", problems)
        if name == "트랙":
            check_conditions(it.get("조건") or {}, f"{p}.조건", problems)


def check_conditions(obj, path, problems):
    """대안조건 선택지·트랙 조건: 칸 이름 → 조건"""
    for k, v in obj.items():
        p = f"{path}.{k}"
        if k in FIELDS:
            check_cell(k, v, p, problems, full=False)
        elif k in LISTS:
            check_list(k, v if isinstance(v, list) else [v], p, problems)
        else:
            problems.append((p, f"알 수 없는 칸: {k}"))


def iter_evidence(obj, path):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k == "근거" and v:
                yield p, v
            else:
                yield from iter_evidence(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_evidence(v, f"{path}[{i}]")


def main():
    out_dir = Path(sys.argv[1])
    text_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "output/texts")
    ev_rows, schema_rows, parse_fail = [], [], []
    files = sorted(p for p in out_dir.glob("PBLN_*.json"))
    for fp in files:
        pid = fp.stem
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            parse_fail.append((pid, str(e)))
            continue
        problems = []
        for k in TOP_KEYS:
            if k not in data:
                problems.append((k, "칸 누락"))
        for k in data:
            if k not in TOP_KEYS:
                problems.append((k, "스키마에 없는 칸"))
        if data.get("공고ID") != pid:
            problems.append(("공고ID", f"파일명과 다름: {data.get('공고ID')!r}"))
        if data.get("스키마버전") != "v0.6":
            problems.append(("스키마버전", f"{data.get('스키마버전')!r}"))
        for name in FIELDS:
            if name in data:
                check_cell(name, data[name], name, problems, full=True)
        for name in LISTS:
            if name in data:
                check_list(name, data[name], name, problems)
        schema_rows += [(pid, p, m) for p, m in problems]

        norm, pos = normalize((text_dir / f"{pid}.txt").read_text(encoding="utf-8"))
        for path, ev in iter_evidence(data, ""):
            n, _ = normalize(ev)
            i = norm.find(n) if n else -1
            ok = i >= 0
            start, end = (pos[i], pos[i + len(n) - 1] + 1) if ok else ("", "")
            ev_rows.append((pid, path, start, end, ok, ev))

    with open(out_dir / "evidence_check.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["공고ID", "칸", "근거_시작", "근거_끝", "근거_검증", "근거"])
        w.writerows(ev_rows)
    with open(out_dir / "schema_check.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["공고ID", "칸", "문제"])
        w.writerows(schema_rows)

    bad_ev = [r for r in ev_rows if not r[4]]
    print(f"파일 {len(files)}개, 파싱 실패 {len(parse_fail)}개")
    for pid, e in parse_fail:
        print(f"  파싱 실패 {pid}: {e}")
    print(f"근거 {len(ev_rows)}개 중 원문에서 못 찾음 {len(bad_ev)}개")
    for r in bad_ev:
        print(f"  {r[0]} {r[1]}: {r[5]}")
    print(f"스키마 문제 {len(schema_rows)}개")
    for r in schema_rows:
        print(f"  {r[0]} {r[1]}: {r[2]}")


if __name__ == "__main__":
    main()
