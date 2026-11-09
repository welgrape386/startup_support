"""
1단계: 검색 대상(시험지) 만들기
- 입력: 팀 원본 스냅샷 1477건 + 예은님 원문 추출 보고서(서비스 범위 342건)
- 출력: docs_snap1016.jsonl (검색 대상 342건)
        docs_snap1016_check.csv (눈으로 확인용 표)
- 원본 스냅샷은 읽기만 하고 절대 수정하지 않음
"""
import json, re, html
from collections import Counter
from pathlib import Path
import pandas as pd

RAG = Path(__file__).resolve().parent.parent
SNAPSHOT = RAG / "01_원본" / "bizinfo_all_20261016_031038.csv"     # 팀 원본 (수정 금지)
TEXTS    = RAG / "01_원본" / "texts_v8_20261024"                    # 10/24 v8 (텍스트 품질 개선, 원문 307건)
REPORT   = TEXTS / "extract_report.csv"                             # 범위 342건 목록
OUT      = Path(__file__).resolve().parent

# ── 1) 범위 342건 고르기 ─────────────────────────────────────
snap = pd.read_csv(SNAPSHOT, encoding="utf-8-sig", dtype=str).fillna("")
scope_ids = set(pd.read_csv(REPORT, encoding="utf-8-sig", dtype=str)["공고ID"])
docs = snap[snap["pblancId"].isin(scope_ids)].copy()
print(f"원본 {len(snap)}건 → 범위 {len(docs)}건")

# ── 2) 지역 칸 만들기 (1차 때와 같은 규칙) ───────────────────
SIDO = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기",
        "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
SEOUL_GU = ["종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구",
            "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구",
            "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구"]

CITY = ["전주", "포항", "구미", "창원", "청주", "천안", "수원", "성남", "김해", "원주", "춘천"]
# 앞이 한글이 아닐 때만 지역명으로 인정 (예: "창업대전"의 '대전'은 지역 아님)
REGION_WORD = re.compile(rf"(?<![가-힣])({'|'.join(SIDO + CITY)})")
# 지자체 이름 (서울특별시, 경상북도, 전남광주통합특별시, 울산광역시 ...)
LOCAL_GOV = re.compile(r"(특별시|광역시|특별자치시|특별자치도|도)$")

def region_of(name, hashtags, jrsd, exc):
    """반환: (지역, 판단근거)  지역 = 서울 / 전국 / 타지역"""
    # 1순위: 제목 앞 [ ]  예) [서울] 종로구 ... / [경북] ...
    m = re.match(r"^\[([^\]]+)\]", name)
    if m:
        return ("서울" if "서울" in m.group(1) else "타지역"), f"제목[{m.group(1)}]"
    # 2순위: 소관기관이 지자체면 그 지역 (예: 울산광역시, 충청남도)
    if LOCAL_GOV.search(jrsd):
        return ("서울" if jrsd.startswith("서울") else "타지역"), f"소관기관 {jrsd}"
    # 3순위: 수행기관·제목에 지역명 (예: 인천창조경제혁신센터, 소담스퀘어 in 경북)
    w = REGION_WORD.search(f"{exc} {name}")
    if w:
        return ("서울" if w.group(1) == "서울" else "타지역"), f"기관·제목 '{w.group(1)}'"
    # 4순위: 해시태그 - 기업마당은 17개 시·도를 다 붙이는 경우가 많아서
    #        일부 시·도만 붙은 경우에만 지역 전용으로 봄
    tags = hashtags.split(",")
    found = {r for r in SIDO if any(r in t for t in tags)}
    if 0 < len(found) < 10:
        return ("서울" if "서울" in found else "타지역"), "해시태그 " + "·".join(sorted(found))
    return "전국", "지역 단서 없음 → 전국"

# 규칙이 틀린 공고를 원문 확인 후 손으로 고친 목록 (공고ID: (지역, 서울구, 원문 근거))
MANUAL = {
    "PBLN_000000000127246": ("전국", [], "원문: 인천 소재·이전 예정 기업은 '해당 여부 기재'만 → 타지역도 신청 가능"),
    "PBLN_000000000127234": ("전국", [], "원문: 신청자격 '전국 예비창업자 및 창업 5년 이내 기업'"),
    "PBLN_000000000126686": ("전국", [], "원문: '전국 17개 센터' 방문·전화·온라인 상담"),
    "PBLN_000000000126865": ("서울", [], "서초창업스테이션 안내 페이지: 서초구는 우대일 뿐 지역 제한 없음 (김나애 확인)"),
    "PBLN_000000000127053": ("전국", [], "원문: 모집대상 '전국 예비창업자 30명' (소관기관 울산광역시라 규칙이 타지역으로 잘못 분류, 주희님 교차검증에서 발견)"),
}

def seoul_gu(name):
    # 서울 공고 중 특정 구 전용인지 (예: [서울] 종로구 ...) → V2 지역 필터에서 사용
    if not name.startswith("[서울]"): return []
    head = name[:40]
    return [g for g in SEOUL_GU if re.search(rf"(^|[\s\]ㆍ·,]){g}", head)]

def clean(text):
    # 사업개요: HTML 기호(&middot; 등) 풀기 + 공백 정리
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()

out = []
for _, d in docs.iterrows():
    reg, why = region_of(d["pblancNm"], d["hashtags"], d["jrsdInsttNm"], d["excInsttNm"])
    gu = seoul_gu(d["pblancNm"])
    if d["pblancId"] in MANUAL:
        reg, gu, note = MANUAL[d["pblancId"]]
        why = f"수작업: {note}"
    txt = TEXTS / "texts" / f'{d["pblancId"]}.txt'
    out.append({
        "pblancId":   d["pblancId"],
        "pblancNm":   clean(d["pblancNm"]),
        "agency":     f'{d["jrsdInsttNm"]} / {d["excInsttNm"]}',
        "summary":    clean(d["bsnsSumryCn"]),         # V0·V1 검색에 쓰는 API 필드
        "region":     reg,
        "region_why": why,
        "seoul_gu":   gu,
        "trgetNm":    d["trgetNm"],
        "field_L":    d["pldirSportRealmLclasCodeNm"],
        "field_M":    d["pldirSportRealmMlsfcCodeNm"],
        "period":     d["reqstBeginEndDe"],
        "url":        d["pblancUrl"],
        "has_text":   txt.exists(),                     # V2에서 원문 사용 가능 여부
    })

# ── 3) 저장 ───────────────────────────────────────────────
with open(OUT / "docs_snap1016.jsonl", "w", encoding="utf-8") as f:
    for d in out: f.write(json.dumps(d, ensure_ascii=False) + "\n")

check = pd.DataFrame(out)[["pblancId", "region", "region_why", "seoul_gu", "pblancNm", "agency",
                           "trgetNm", "field_L", "field_M", "has_text"]]
check["seoul_gu"] = check["seoul_gu"].apply(" ".join)
check.sort_values(["region", "pblancNm"]).to_csv(OUT / "docs_snap1016_check.csv",
                                                 index=False, encoding="utf-8-sig")

# DB 공고 테이블용 지역 칸 (민지님) : 공고ID → 지역 / 서울 구 전용 / 원문 유무
pd.DataFrame([{"pblancId": d["pblancId"], "region": d["region"],
               "seoul_gu": ",".join(d["seoul_gu"]) or None, "has_text": int(d["has_text"])} for d in out])   .to_csv(OUT / "region_map.csv", index=False, encoding="utf-8-sig")

# ── 4) 요약 출력 ──────────────────────────────────────────
print("지역:", dict(Counter(d["region"] for d in out)))
print("서울 구 전용:", sum(1 for d in out if d["seoul_gu"]), "건")
print("수작업 수정:", sum(1 for d in out if d["region_why"].startswith("수작업")), "건")
print("원문 텍스트 있음:", sum(d["has_text"] for d in out), "건 / 없음(사업개요로 대체):",
      sum(not d["has_text"] for d in out), "건")
print("서울+전국(서울 사용자가 실제로 쓸 수 있는 공고):",
      sum(d["region"] in ("서울", "전국") for d in out), "건")
print("저장:", OUT / "docs_snap1016.jsonl")
