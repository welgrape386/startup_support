"""
fetch_bizinfo.py - 기업마당 지원사업 공고 전체를 CSV로 저장

사용:
    python fetch_bizinfo.py                    # data/bizinfo_all_YYYYMMDD_HHMMSS.csv 저장
    python fetch_bizinfo.py --out_dir output   # 다른 폴더에 저장
    python fetch_bizinfo.py --page_unit 200

실행할 때마다 수집 시각을 붙인 새 파일로 저장한다. 기존 CSV는 덮어쓰지 않는다.
"""

import argparse, csv, os, sys, time
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')


# =============================================
# 설정
# =============================================

BIZINFO_KEY = os.environ.get("BIZINFO_KEY")
if not BIZINFO_KEY:
    raise RuntimeError("BIZINFO_KEY 환경변수가 설정되지 않았습니다.")

API_URL  = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
CSV_DIR  = Path(__file__).resolve().parent / "data"
CSV_STEM = "bizinfo_all"
PAGE_DELAY = 0.5  # 요청 사이 대기(초) - 기업마당 서버 부담 줄이기

# CSV 헤더는 API 필드명 그대로 쓴다 (extract_texts.py 등 팀 코드가 이 이름으로 읽음)
# 주석은 필드 의미. 목록에 없는 새 필드가 오면 뒤에 붙여 저장한다.
COLUMNS = [
    "pblancId",                    # 공고ID
    "pblancNm",                    # 공고명
    "jrsdInsttNm",                 # 소관기관
    "excInsttNm",                  # 수행기관
    "pldirSportRealmLclasCodeNm",  # 지원분야(대)
    "pldirSportRealmMlsfcCodeNm",  # 지원분야(중)
    "trgetNm",                     # 지원대상
    "reqstBeginEndDe",             # 신청기간
    "reqstMthPapersCn",            # 신청방법
    "bsnsSumryCn",                 # 사업개요
    "refrncNm",                    # 문의처
    "hashtags",                    # 해시태그
    "pblancUrl",                   # 공고URL
    "rceptEngnHmpgUrl",            # 접수기관 홈페이지
    "printFileNm",                 # 본문출력파일명
    "printFlpthNm",                # 본문출력파일URL
    "fileNm",                      # 첨부파일명 (여러 개면 @로 구분)
    "flpthNm",                     # 첨부파일URL (여러 개면 @로 구분)
    "inqireCo",                    # 조회수
    "creatPnttm",                  # 등록일시
    "updtPnttm",                   # 수정일시
]
SKIP_FIELDS = {"totCnt"}

# HTML이 섞여 오는 필드
HTML_FIELDS = {"bsnsSumryCn", "reqstMthPapersCn"}


# =============================================
# 수집
# =============================================

def fetch_page(page_index: int, page_unit: int) -> list[dict]:
    params = {
        "crtfcKey":  BIZINFO_KEY,
        "dataType":  "json",
        "pageUnit":  page_unit,
        "pageIndex": page_index,
    }
    for attempt in range(3):
        try:
            res = requests.get(API_URL, params=params, timeout=60)
            res.raise_for_status()
            data = res.json()
            if "reqErr" in data:
                raise RuntimeError(f"API 오류: {data['reqErr']}")
            return data.get("jsonArray", [])
        except (requests.RequestException, ValueError) as e:
            print(f"  [재시도 {attempt + 1}/3] page {page_index}: {e}")
            time.sleep(2)
    raise RuntimeError(f"page {page_index} 수집 실패")


def fetch_all(page_unit: int) -> list[dict]:
    items, seen = [], set()
    page = 1
    while True:
        rows = fetch_page(page, page_unit)
        if not rows:
            break
        total = int(rows[0].get("totCnt") or 0)
        for r in rows:
            if r["pblancId"] not in seen:
                seen.add(r["pblancId"])
                items.append(r)
        print(f"  page {page}: {len(items)}/{total}")
        if len(rows) < page_unit or len(items) >= total:
            break
        page += 1
        time.sleep(PAGE_DELAY)
    return items


# =============================================
# 저장
# =============================================

def clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def html_to_text(value) -> str:
    text = BeautifulSoup(clean(value), "html.parser").get_text("\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def new_csv_path(out_dir: Path) -> Path:
    return out_dir / f"{CSV_STEM}_{datetime.now():%Y%m%d_%H%M%S}.csv"


def save_csv(items: list[dict], csv_path: Path):
    extra = sorted({k for it in items for k in it} - set(COLUMNS) - SKIP_FIELDS)
    columns = COLUMNS + extra
    if extra:
        print(f"  새 필드 발견 (뒤에 추가): {extra}")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    # "x": 이미 있는 파일이면 덮어쓰지 않고 에러
    with open(csv_path, "x", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for it in items:
            writer.writerow([
                html_to_text(it.get(k)) if k in HTML_FIELDS else clean(it.get(k))
                for k in columns
            ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--page_unit", type=int, default=500, help="페이지당 건수")
    parser.add_argument("--out_dir", type=Path, default=CSV_DIR, help="CSV 저장 폴더")
    args = parser.parse_args()

    print("기업마당 공고 수집 시작")
    items = fetch_all(args.page_unit)
    csv_path = new_csv_path(args.out_dir)
    save_csv(items, csv_path)
    print(f"완료: {len(items)}건 → {csv_path}")


if __name__ == "__main__":
    main()
