"""v3 추출 결과 30건의 업종 칸에 `업종명`(원문 업종 키워드)을 붙여 새 폴더에 저장한다 (원본은 그대로)

사용법: python add_industry_names.py
출력: results/extract_v3_terra_업종명/ (공고별 JSON 30개, conditions_v3_terra_업종명.json, 업종명_목록.csv)

- 업종명 = {"허용": [...], "제외": [...]}. 팀 카테고리(5개) 매칭용
- 키워드는 원문에 글자 그대로 있는 말만 (공백 무시하고 원문에서 찾아 확인). 2026-11-11 Claude가 업종·사업분야 근거를 보고 골랐다
- 모으는 곳: 업종 칸 근거(제외 업종 나열), 기타조건(구분: 사업분야) 근거(되는 업종·안 되는 업종)
- "소상공인 정책자금 융자제외 대상 업종"처럼 표준 목록을 가리키기만 하는 말은 넣지 않는다 → `제외_참조` + excluded/excluded_industries.csv
- 사업분야라도 업종이 아닌 조건("온라인으로 상품 판매 가능", "제품 개발 완료")은 넣지 않는다
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = [ROOT / "results/extract_v3_dev_terra", ROOT / "results/extract_v3_eval_terra"]
OUT = ROOT / "results/extract_v3_terra_업종명"
TEXTS = ROOT / "output/texts"

# 공고ID 뒤 6자리 → 위치("최상위" 또는 트랙 이름) → {"허용": [...], "제외": [...]}
KEYWORDS = {
    # 개발 15
    # 11/13: 표준 목록의 별명("사치향락업종", "도박·투기·사치")·제외_참조 공고의 예시는 넣지 않음 → 119017·123842·123844·127250·118350 비움 (실제 업종은 expand_industry_refs.py가 CSV에서 채움)
    # 11/12: 자격 문장의 큰 이름("농업, 농촌, 식품 및 관련 분야")도 넣고, "수산기업에 해당하는 경우 지원에서 배제" 추가 (v4 개발 실행에서 발견)
    "119567": {"최상위": {"허용": ["농업, 농촌, 식품 및 관련 분야", "농식품", "농작물 재배 및 유통·가공업", "식품 관련업", "축산업",
                                "반려동물 산업", "임업", "곤충 관련업"],
                        "제외": ["수산기업"]}},
    "121175": {"최상위": {"허용": ["기술창업"], "제외": ["단순 카페 운영", "도·소매", "유통"]}},
    "123795": {"업종칸있는트랙": {"제외": ["사치향락적 소비‧투기 조장 업종"]}},
    # 허용은 신청 자격에 나온 업종만. 예시("~ 등")·우대 업종은 넣지 않는다 (11/11 팀 요청)
    # "에너지 절감, 온실가스 저감 등"은 환경 관련성의 예시라 뺌
    "124045": {"최상위": {"허용": ["녹색분야", "기후기술"]}},
    "126686": {"최상위": {"허용": ["기술창업"], "제외": ["단순 카페 운영", "도·소매", "유통"]}},
    "126969": {"최상위": {"허용": ["ICT기업"]}},
    "127098": {"최상위": {"제외": ["일반유흥주점업", "무도유흥주점업", "기타 주점업", "카지노 운영업", "기타 사행시설 관리 및 운영업"]}},
    # 평가 15
    "121291": {"최상위": {"제외": "업종.제외"}},  # 원문 [별표 2] 28개 = 추출 결과 업종.제외 그대로
    "126965": {"소공인특화자금": {"허용": ["제조업"]}},
    # "음식업, 소매업, 서비스업, 제조업 등 다양한 업종 지원 가능"은 생활밀접업종의 예시라 뺌
    "127032": {"최상위": {"허용": ["생활밀접업종"], "제외": ["무인 점포", "프랜차이즈 업종", "단란·유흥주점", "비디오감상실", "안마시술소"]}},
    # 괄호 안 "AI, 사이버보안, … 딥테크 등"은 전시분야의 예시라 뺌
    "127132": {"최상위": {"허용": ["4YFN 전시분야"]}},
    "127234": {"최상위": {"허용": ["핀테크", "지역 금융", "농생명 금융", "AI 금융", "데이터 금융", "기후·에너지 금융"],
                        "제외": ["가상자산 거래소 등 가상자산의 매매·중개·교환", "금융·보험업", "대부업·대부중개업", "불법 사금융업"]}},
}
EMPTY_UPJONG = {"상태": "없음", "포함": None, "제외": None, "포함_대분류": None, "제외_대분류": None,
                "KSIC코드": None, "제외_참조": None, "근거": None}


def squash(s):
    return re.sub(r"\s+", "", s)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, missing, merged = [], [], []
    for src in SRC:
        for p in sorted(src.glob("PBLN_*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            pid = d["공고ID"]
            raw = squash((TEXTS / f"{pid}.txt").read_text(encoding="utf-8"))
            spec = KEYWORDS.get(pid[-6:], {})
            # 모든 업종 칸(최상위·트랙)에 빈 업종명부터
            targets = {"최상위": d.setdefault("업종", dict(EMPTY_UPJONG))}
            for t in d.get("트랙") or []:
                cond = t.setdefault("조건", {})
                if "업종" in cond:
                    targets[t.get("이름")] = cond["업종"]
                    if "업종칸있는트랙" in spec and cond["업종"].get("근거"):
                        targets["업종칸있는트랙"] = cond["업종"]
            for cell in targets.values():
                cell["업종명"] = {"허용": [], "제외": []}
            for where, kw in spec.items():
                if where not in targets:  # 트랙에 업종 칸이 없으면 만들어서 붙임
                    t = next(t for t in d["트랙"] if t.get("이름") == where)
                    targets[where] = t["조건"].setdefault("업종", {"상태": "없음"})
                    targets[where]["업종명"] = {"허용": [], "제외": []}
                cell = targets[where]
                for side in ("허용", "제외"):
                    words = kw.get(side, [])
                    if words == "업종.제외":
                        words = []
                        for x in cell.get("제외") or []:
                            # 원문은 "주류(46331) 및 담배 도매업(46333)": 코드가 사이에 있어 원문대로 둘로 나눔
                            words += ["주류", "담배 도매업"] if x == "주류 및 담배 도매업" else [x]
                    for w in words:
                        if squash(w) not in raw:
                            missing.append((pid, where, side, w))
                    cell["업종명"][side] = words
                    for w in words:
                        rows.append({"공고ID": pid, "분할": "개발" if "dev" in src.name else "평가",
                                     "위치": "트랙" if where != "최상위" else "최상위", "허용_제외": side, "업종명": w})
            (OUT / p.name).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            merged.append(d)
            if not spec:
                rows.append({"공고ID": pid, "분할": "개발" if "dev" in src.name else "평가", "위치": "", "허용_제외": "",
                             "업종명": "(없음)"})
    (OUT / "conditions_v3_terra_업종명.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(OUT / "업종명_목록.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["공고ID", "분할", "위치", "허용_제외", "업종명"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(merged)}건 저장, 키워드 {sum(r['업종명'] != '(없음)' for r in rows)}개, 키워드 없는 공고 {sum(r['업종명'] == '(없음)' for r in rows)}건")
    print("원문에 없는 키워드:", missing or "없음")


if __name__ == "__main__":
    main()
