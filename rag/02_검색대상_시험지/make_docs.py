"""
검색 대상 342건 만들기

    python make_docs.py

입력: 01_원본의 기업마당 스냅샷(1477건) + 예은님 추출 보고서(범위 342건)
출력: docs_snap1016.jsonl  검색 대상
      docs_snap1016_check.csv  눈으로 확인용
      region_map.csv  공고ID → 지역, 서울 구, 원문 유무 (BE 공고 테이블용)
01_원본은 읽기만 함
"""
import json, re, html
from collections import Counter
from pathlib import Path
import pandas as pd

RAG = Path(__file__).resolve().parent.parent
SNAPSHOT = RAG / "01_원본" / "bizinfo_all_20261016_031038.csv"
TEXTS    = RAG / "01_원본" / "texts_v8_20261024"
REPORT   = TEXTS / "extract_report.csv"
OUT      = Path(__file__).resolve().parent

snap = pd.read_csv(SNAPSHOT, encoding="utf-8-sig", dtype=str).fillna("")
scope_ids = set(pd.read_csv(REPORT, encoding="utf-8-sig", dtype=str)["공고ID"])
docs = snap[snap["pblancId"].isin(scope_ids)].copy()
print(f"원본 {len(snap)}건 중 범위 {len(docs)}건")

# 지역 판단 ------------------------------------------------------------
SIDO = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기",
        "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
SEOUL_GU = ["종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구",
            "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구",
            "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구"]
CITY = ["전주", "포항", "구미", "창원", "청주", "천안", "수원", "성남", "김해", "원주", "춘천"]
REGION_WORD = re.compile(rf"(?<![가-힣])({'|'.join(SIDO + CITY)})")   # '창업대전'의 대전은 제외
LOCAL_GOV = re.compile(r"(특별시|광역시|특별자치시|특별자치도|도)$")

def region_of(name, hashtags, jrsd, exc):
    """(서울/전국/타지역, 근거). 제목 [지역] → 소관기관 → 기관·제목 속 지역명 → 해시태그 순"""
    m = re.match(r"^\[([^\]]+)\]", name)
    if m:
        return ("서울" if "서울" in m.group(1) else "타지역"), f"제목[{m.group(1)}]"
    if LOCAL_GOV.search(jrsd):
        return ("서울" if jrsd.startswith("서울") else "타지역"), f"소관기관 {jrsd}"
    w = REGION_WORD.search(f"{exc} {name}")
    if w:
        return ("서울" if w.group(1) == "서울" else "타지역"), f"기관·제목 '{w.group(1)}'"
    # 기업마당은 지방 공고에도 17개 시도를 다 붙이는 경우가 많아서 일부만 붙은 경우만 인정
    found = {r for r in SIDO if any(r in t for t in hashtags.split(","))}
    if 0 < len(found) < 10:
        return ("서울" if "서울" in found else "타지역"), "해시태그 " + "·".join(sorted(found))
    return "전국", "지역 단서 없음 → 전국"

# 원문을 보고 직접 고친 공고: 공고ID → (지역, 서울 구, 근거)
MANUAL = {
    "PBLN_000000000127246": ("전국", [], "원문: 인천 소재·이전 예정 기업은 '해당 여부 기재'만 → 타지역도 신청 가능"),
    "PBLN_000000000127234": ("전국", [], "원문: 신청자격 '전국 예비창업자 및 창업 5년 이내 기업'"),
    "PBLN_000000000126686": ("전국", [], "원문: '전국 17개 센터' 방문·전화·온라인 상담"),
    "PBLN_000000000126865": ("서울", [], "서초창업스테이션 안내 페이지: 서초구는 우대일 뿐 지역 제한 없음 (김나애 확인)"),
    "PBLN_000000000127053": ("전국", [], "원문: 모집대상 '전국 예비창업자 30명' (소관기관 울산광역시라 규칙이 타지역으로 잘못 분류, 주희님 교차검증에서 발견)"),
}

def seoul_gu(name):
    """[서울] 종로구 … 처럼 특정 구 전용 공고면 그 구 목록"""
    if not name.startswith("[서울]"): return []
    return [g for g in SEOUL_GU if re.search(rf"(^|[\s\]ㆍ·,]){g}", name[:40])]

def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()

out = []
for _, d in docs.iterrows():
    reg, why = region_of(d["pblancNm"], d["hashtags"], d["jrsdInsttNm"], d["excInsttNm"])
    gu = seoul_gu(d["pblancNm"])
    if d["pblancId"] in MANUAL:
        reg, gu, note = MANUAL[d["pblancId"]]
        why = f"수작업: {note}"
    out.append({
        "pblancId":   d["pblancId"],
        "pblancNm":   clean(d["pblancNm"]),
        "agency":     f'{d["jrsdInsttNm"]} / {d["excInsttNm"]}',
        "summary":    clean(d["bsnsSumryCn"]),
        "region":     reg,
        "region_why": why,
        "seoul_gu":   gu,
        "trgetNm":    d["trgetNm"],
        "field_L":    d["pldirSportRealmLclasCodeNm"],
        "field_M":    d["pldirSportRealmMlsfcCodeNm"],
        "period":     d["reqstBeginEndDe"],
        "url":        d["pblancUrl"],
        "has_text":   (TEXTS / "texts" / f'{d["pblancId"]}.txt').exists(),
    })

# 저장 ----------------------------------------------------------------
with open(OUT / "docs_snap1016.jsonl", "w", encoding="utf-8") as f:
    for d in out: f.write(json.dumps(d, ensure_ascii=False) + "\n")

check = pd.DataFrame(out)[["pblancId", "region", "region_why", "seoul_gu", "pblancNm", "agency",
                           "trgetNm", "field_L", "field_M", "has_text"]]
check["seoul_gu"] = check["seoul_gu"].apply(" ".join)
check.sort_values(["region", "pblancNm"]).to_csv(OUT / "docs_snap1016_check.csv", index=False, encoding="utf-8-sig")

pd.DataFrame([{"pblancId": d["pblancId"], "region": d["region"], "seoul_gu": ",".join(d["seoul_gu"]) or None,
               "has_text": int(d["has_text"])} for d in out]).to_csv(OUT / "region_map.csv", index=False, encoding="utf-8-sig")

print("지역:", dict(Counter(d["region"] for d in out)))
print("서울 구 전용:", sum(1 for d in out if d["seoul_gu"]), "건 / 수작업:", len(MANUAL), "건")
print("원문 있음:", sum(d["has_text"] for d in out), "건 / 없음:", sum(not d["has_text"] for d in out), "건")
print("서울+전국:", sum(d["region"] in ("서울", "전국") for d in out), "건")
