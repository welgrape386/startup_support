"""공고 데이터 CSV 4개 → 공고ID별 정보 사전. 서버가 켜질 때 한 번만 읽는다.

data/files/
  benefit_summary_62.csv  (혜택요약)    공고ID, 공고명, 혜택요약, 근거                     → title, benefit_summary
  max_amount_62.csv       (최대지원금)  공고ID, 최대지원금_받는돈 / 융자·투자 / R&D (만원)  → amt_grant, amt_loan_invest, amt_rnd
  category_map.csv        (카테고리)    pblancId + 공고 카테고리 9개 원핫                   → category
  support_types_62.csv    (지원유형)    공고ID + 지원유형 21개 원핫                         → support_types

파일 이름은 영어로 둔다. 한글 파일 이름은 Windows 압축 풀기·git에서 깨지거나 빠질 수 있다.

판정 결과(signal)와 마감일은 여기에 없다. 판정 파트·백엔드에서 받는다 (core/inputs.py).
나중에 DB로 옮기면 이 파일만 DB 조회로 바꾸면 된다.
"""
import csv
from pathlib import Path

FILES = Path(__file__).parent / "files"

CATEGORIES = ["자금", "교육·컨설팅", "공간·시설", "홍보·판매", "인력", "기술개발", "해외진출", "제도·인증", "기타"]
SUPPORT_TYPES = ["보조금·사업화자금", "시상금", "인건비·수당", "융자·보증·카드", "R&D 자금", "투자·IR",
                 "비용감면·환급", "바우처", "판로(입점·유통)", "홍보·마케팅", "장비·시설(현물·이용)",
                 "시제품·제품개발", "기술(시험·평가·이전)", "물류·통관", "컨설팅·상담", "교육", "법률",
                 "매칭·네트워킹", "인증·조달", "포상", "해외진출"]
AMOUNT_COLS = {"amt_grant": "최대지원금_받는돈(만원)",
               "amt_loan_invest": "최대지원금_융자·투자(만원)",
               "amt_rnd": "최대지원금_R&D(만원)"}


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _num(v):
    v = (v or "").replace(",", "").strip()
    return float(v) if v else None


def _onehot(row, names):
    return [n for n in names if str(row.get(n, "")).strip() == "1"]


def load_announcements(benefit_csv=FILES / "benefit_summary_62.csv",
                       amount_csv=FILES / "max_amount_62.csv",
                       category_csv=FILES / "category_map.csv",
                       support_type_csv=FILES / "support_types_62.csv") -> dict:
    ann = {r["공고ID"]: {"title": r["공고명"].strip(),
                         "benefit_summary": r["혜택요약"].strip(),
                         "amt_grant": None, "amt_loan_invest": None, "amt_rnd": None,
                         "category": [], "support_types": []}
           for r in _rows(benefit_csv)}
    for r in _rows(amount_csv):
        if r["공고ID"] in ann:
            ann[r["공고ID"]].update({k: _num(r.get(c)) for k, c in AMOUNT_COLS.items()})
    for r in _rows(category_csv):
        if r["pblancId"] in ann:
            ann[r["pblancId"]]["category"] = _onehot(r, CATEGORIES)
    for r in _rows(support_type_csv):
        if r["공고ID"] in ann:
            ann[r["공고ID"]]["support_types"] = _onehot(r, SUPPORT_TYPES)
    return ann
