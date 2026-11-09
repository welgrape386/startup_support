"""
지원 종류 꼬리표 만들기 → category_map.csv (화면 카테고리 필터용, 기능명세서 3.3.1)

카테고리 9개 (1차 보고서에서 정의): 자금 / 교육·컨설팅 / 공간·시설 / 홍보·판매 / 인력 / 기술개발 / 해외진출 / 제도·인증 / 기타
- 공고 하나가 여러 카테고리에 들어갈 수 있음 (1차 원칙)
- 꼬리표 = ① API 지원분야(대/중분류) 매핑 + ② 공고명·지원내용 키워드 → 합침
- 둘 다 없으면 '기타'
- 1차 때는 ①만 써서 '경영/디자인·상품화·사업화'(342건 중 62건)가 전부 기타로 갔음
  → 대부분 카드수수료·보험료·바우처 같은 '돈 주는' 공고라 ②로 보완

입력: docs_snap1016.jsonl / 출력: category_map.csv, category_map_check.csv(눈으로 확인용)
"""
import json, re
from collections import Counter
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
CATS = ["자금", "교육·컨설팅", "공간·시설", "홍보·판매", "인력", "기술개발", "해외진출", "제도·인증", "기타"]

# ① API 지원분야 → 카테고리 (1차 매핑 + 342건에 새로 나온 분야)
API_MAP = {
    ("금융", "융자"): ["자금"], ("금융", "보증"): ["자금"], ("금융", "펀드/투자"): ["자금"],
    ("금융", "보험(수출+무역)"): ["해외진출"],
    ("창업", "사업화지원"): ["자금", "교육·컨설팅"],        # 1차: 자금 + 교육·컨설팅 둘 다
    ("창업", "예비창업자지원"): ["자금", "교육·컨설팅"],
    ("창업", "창업정보제공"): ["교육·컨설팅"],
    ("창업", "창업공간지원"): ["공간·시설"],
    ("창업", "재기지원"): ["교육·컨설팅"],                 # 새로 나온 분야
    ("경영", "컨설팅"): ["교육·컨설팅"], ("경영", "교육"): ["교육·컨설팅"],
    ("경영", "시설/입지지원"): ["공간·시설"],
    ("경영", "디자인/상품화/사업화"): [],                   # 1차: 기타 → 키워드로 판단
    ("내수", "홍보지원"): ["홍보·판매"], ("내수", "온라인"): ["홍보·판매"],
    ("내수", "오프라인"): ["홍보·판매"], ("내수", "공공구매"): ["홍보·판매"],
    ("기타", "제도"): ["제도·인증"],
}
API_BY_L = {"인력": ["인력"], "기술": ["기술개발"], "수출": ["해외진출"]}   # 대분류 전체

# ② 공고명 + 지원내용 키워드 → 카테고리
KEYWORDS = {   # 너무 넓은 말('자금', '투자', '인력', '상담')은 빼거나 좁힘 → 엉뚱한 꼬리표 방지
    "자금": r"융자|대출|보증|정책자금|지원금|사업화 ?자금|크라우드펀딩|바우처|수수료 ?지원|보험료|보험금|보조금|이차보전|이자 ?지원|비용 ?지원|지역화폐|상품권|사회보험|직접투자|투자금|매칭 ?융자|(?<![A-Za-z])IR(?![A-Za-z])|인센티브",
    "교육·컨설팅": r"교육|컨설팅|멘토링|(?<!MD )(?<!MD)상담|코칭|아카데미|진단|클리닉|자문|액셀러레이팅",
    "공간·시설": r"공간|입주|시설|장비|공유주방|점포|매장|인테리어|리모델링|간판|공장|작업장|스튜디오|임차|보육",
    "홍보·판매": r"판로|(?<![A-Za-z])MD(?![A-Za-z])|홍보|마케팅|판매|라이브 ?커머스|홈쇼핑|입점|전시회|박람회|쇼핑몰|상세페이지|기획전|팝업|택배|배달|포장재|온라인 ?플랫폼|구매",
    "인력": r"채용|인건비|고용 ?지원|일자리|인턴",
    "기술개발": r"R&D|기술개발|시제품|특허|지식재산|(?<![A-Za-z])IP(?![A-Za-z])|상표|기술평가|기술이전|실증",
    "해외진출": r"해외|수출|글로벌",
    "제도·인증": r"인증|확인서|포상|시상|표창",
}

# 지원 내용이 추상적이라 규칙으로 못 잡는 공고 (1차 때도 예외 처리했던 것)
MANUAL = {
    "PBLN_000000000117016": ["자금", "교육·컨설팅", "공간·시설", "홍보·판매"],   # 소상공인 지원사업 통합공고 (육성·성장·상권·디지털·경영부담 완화·재기)
}

def support_text(d):
    """공고명 + 사업개요의 '지원내용' 부분 (사업개요는 '☞ 지원대상 ☞ 지원내용' 구조)
    지원대상 부분은 빼야 '융자를 받은 기업' 같은 대상 설명이 꼬리표로 잘못 들어가지 않음"""
    parts = d["summary"].split("☞")
    content = parts[2] if len(parts) >= 3 else d["summary"]
    return f'{d["pblancNm"]} {content}'

rows = []
for l in open(HERE / "docs_snap1016.jsonl", encoding="utf-8"):
    d = json.loads(l)
    from_api = API_MAP.get((d["field_L"], d["field_M"]), API_BY_L.get(d["field_L"], []))
    text = support_text(d)
    from_kw = {c: m.group(0) for c, p in KEYWORDS.items() if (m := re.search(p, text))}
    cats = [c for c in CATS if c in from_api or c in from_kw] or ["기타"]
    why = [f"API {d['field_L']}/{d['field_M']}"] if from_api else []
    if d["pblancId"] in MANUAL:
        cats, why, from_kw = MANUAL[d["pblancId"]], ["수작업 (통합공고)"], {}
    why += [f"{c}←'{w}'" for c, w in from_kw.items() if c not in from_api]
    rows.append({"pblancId": d["pblancId"], "카테고리": ", ".join(cats), "공고명": d["pblancNm"],
                 "지역": d["region"], "API분야": f"{d['field_L']}/{d['field_M']}", "근거": ", ".join(why) or "없음 → 기타",
                 **{c: int(c in cats) for c in CATS}})

df = pd.DataFrame(rows)
df[["pblancId", "카테고리"] + CATS].to_csv(HERE / "category_map.csv", index=False, encoding="utf-8-sig")
df[["pblancId", "지역", "공고명", "카테고리", "근거", "API분야"]].sort_values(["지역", "카테고리"]) \
  .to_csv(HERE / "category_map_check.csv", index=False, encoding="utf-8-sig")

print("저장: category_map.csv (공고ID → 카테고리, 카테고리별 0/1 칸)")
for scope, sub in [("전체 342건", df), (f"서울+전국 {(df['지역'] != '타지역').sum()}건", df[df["지역"] != "타지역"])]:
    print(f"\n[{scope}] 카테고리별 공고 수:", {c: int(sub[c].sum()) for c in CATS})
    print("  공고당 카테고리 수:", dict(sorted(Counter(sub["카테고리"].str.count(", ") + 1).items())))
