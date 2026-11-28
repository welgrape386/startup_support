"""B0 기준선: 원문을 읽지 않고 기업마당 API 필드만으로 자격 조건 JSON을 채운다 (11/17)

목적: 추출 성능 비교. B0(API만) vs B1(LLM 원문 추출, extract_v4). 같은 채점(compare_gold.py), 같은 평가 15건
사용법: python b0_api_extract.py  → results/b0_api_eval15/ 에 공고별 JSON + compare_gold 실행

API로 채울 수 있는 칸만 규칙으로 채움 (나머지 칸은 API에 정보가 없어 상태 "없음")
- 신청자_유형: 지원대상(trgetNm)
    · "창업벤처" → 예비창업자·개인사업자·법인 (창업 공고는 예비창업자도 받는 경우가 많음)
    · 그 외(소상공인·중소기업 등) → 개인사업자·법인
- 지역: 소관기관(jrsdInsttNm)이 시도(○○특별시·광역시·도)이면 그 시도 + 공고명 머리말의 구 이름("[서울] 은평구 …")
    · 유형은 API에 없으므로 가장 흔한 "사업장소재지"로 둠
    · 소관기관이 중앙부처면 지역 제한 없음
- 나이·업력·사업자등록·창업이력·업종·기업규모·제외대상: API에 칸이 없음 → "없음"
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results/b0_api_eval15"
IDS = (ROOT / "prompts/target_ids_gold30_v5_eval.txt").read_text().split()
SIDO = re.compile(r"(특별시|광역시|특별자치시|특별자치도|도)$")
GU = re.compile(r"^\[[^\]]+\]\s*([가-힣]+[구군시])[\s·ㆍ,]")
NONE = {"상태": "없음"}


def build(r):
    t = r["trgetNm"]
    types = ["예비창업자", "개인사업자", "법인"] if "창업" in t else ["개인사업자", "법인"]
    region = NONE
    agency = r["jrsdInsttNm"].strip()
    if SIDO.search(agency):
        m = GU.match(r["pblancNm"])
        region = {"상태": "있음", "범위": [{"시도": agency, "권역": None, "시군구": m.group(1) if m else None}],
                  "유형": ["사업장소재지"], "유형_결합": None, "기준일": "명시없음", "사후충족_허용": None,
                  "사후충족_기한": None, "근거": None}
    d = {"공고ID": r["pblancId"], "스키마버전": "B0-API", "신청자_유형": {"상태": "있음", "값": types, "근거": None},
         "지역": region}
    for k in ("나이", "성별", "업력", "사업자등록", "창업이력", "업종", "기업규모"):
        d[k] = dict(NONE)
    for k in ("보유요건", "특수자격", "제외대상", "대안조건", "기타조건", "트랙"):
        d[k] = []
    return d


def main():
    api = {}
    for f in sorted((ROOT / "data").glob("bizinfo_all_*.csv")):
        with open(f, encoding="utf-8-sig") as fh:
            api.update({r["pblancId"]: r for r in csv.DictReader(fh)})
    OUT.mkdir(parents=True, exist_ok=True)
    for pid in IDS:
        (OUT / f"{pid}.json").write_text(json.dumps(build(api[pid]), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"B0 {len(IDS)}건 → {OUT}")
    subprocess.run([sys.executable, str(ROOT / "compare_gold.py"), str(OUT)], check=True)


if __name__ == "__main__":
    main()
