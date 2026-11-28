"""판정 평가용 48건 패키지를 만든다 (11/24, 나애님 사용자 샘플 + 나주희님 라벨링에 맞춤)

사용법: python make_judge_eval48.py
입력: delivery/서비스데이터_62_20261119/공고목록_RAG8.csv (48건 목록)
출력: delivery/판정평가_RAG48_20261124/ (+ .zip)
  - LLM추출_48/ : 48건 모두 LLM 원본 추출 (사람 수정·정답 JSON 없음 = 실제 성능)
      · 정답셋 30에 든 공고 → results/eval_v4_30_업종확장 (판정평가_30 패키지의 LLM추출_30과 같은 것)
      · 나머지 → results/extract_v4_all_terra_업종확장 (manual_fixes 적용 전)
  - 원문_48/    : output/texts (추출에 쓴 텍스트)
  - API필드_48.csv : 기업마당 API 스냅샷 2026-10-16 (API필드_30.csv와 같은 열)
"""
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIST = ROOT / "delivery/서비스데이터_62_20261119/공고목록_RAG8.csv"
EVAL30 = ROOT / "results/eval_v4_30_업종확장"
ALL = ROOT / "results/extract_v4_all_terra_업종확장"
TEXTS = ROOT / "output/texts"
API = ROOT / "data/bizinfo_all_20261016_031038.csv"
SPLIT = ROOT / "delivery/판정평가_20261119/분할.csv"
OUT = ROOT / "delivery/판정평가_RAG48_20261124"

API_COLS = [("공고ID", "pblancId"), ("공고명", "pblancNm"), ("소관기관", "jrsdInsttNm"), ("수행기관", "excInsttNm"),
            ("분야_대", "pldirSportRealmLclasCodeNm"), ("분야_중", "pldirSportRealmMlsfcCodeNm"), ("지원대상", "trgetNm"),
            ("사업개요", "bsnsSumryCn"), ("접수기간", "reqstBeginEndDe"), ("신청방법", "reqstMthPapersCn"),
            ("해시태그", "hashtags"), ("공고URL", "pblancUrl")]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "LLM추출_48").mkdir(parents=True)
    (OUT / "원문_48").mkdir()
    rows = list(csv.DictReader(open(LIST, encoding="utf-8-sig")))
    ids = [r["pblancId"] for r in rows]
    split = {r["공고ID"]: r["분할"] for r in csv.DictReader(open(SPLIT, encoding="utf-8-sig"))}

    merged, src_rows = [], []
    for pid in ids:
        src = EVAL30 / f"{pid}.json" if (EVAL30 / f"{pid}.json").exists() else ALL / f"{pid}.json"
        shutil.copyfile(src, OUT / "LLM추출_48" / f"{pid}.json")
        merged.append(json.loads(src.read_text(encoding="utf-8")))
        shutil.copyfile(TEXTS / f"{pid}.txt", OUT / "원문_48" / f"{pid}.txt")
        src_rows.append({"공고ID": pid, "정답셋30": "O" if pid in split else "",
                         "분할": split.get(pid, "추가"), "LLM추출 출처": src.parent.name})
    (OUT / "LLM추출_48" / "conditions_llm_48.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    api = {r["pblancId"]: r for r in csv.DictReader(open(API, encoding="utf-8-sig"))}
    with open(OUT / "API필드_48.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in API_COLS] + ["분할"])
        for pid in ids:
            w.writerow([api[pid][c] for _, c in API_COLS] + [split.get(pid, "추가")])
    with open(OUT / "목록_48.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(src_rows[0]))
        w.writeheader()
        w.writerows(src_rows)
    shutil.copyfile(ROOT / "excluded/excluded_industries.csv", OUT / "excluded_industries.csv")
    print(f"{len(ids)}건 → {OUT.name} (정답셋 공고 {sum(r['정답셋30'] == 'O' for r in src_rows)})")


if __name__ == "__main__":
    main()
