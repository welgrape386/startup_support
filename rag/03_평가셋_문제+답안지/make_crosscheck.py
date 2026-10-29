"""
교차 검증용 40줄 뽑기 (주희님 ↔ 김나애, 서로의 정답지를 40개씩 채점해서 일치도 확인)

- 입력: pool_snap1016.xlsx (답안지 752줄)
- 출력: 교차검증_주희님용_40.xlsx   → 주희님께 보냄. 내 점수·이유를 가린 블라인드 시트 + 채점기준
        교차검증_정답비교_40.xlsx   → 내가 보관. 내 점수 + 주희님 점수 붙여넣을 칸 + 일치 여부
- 뽑는 방법: 자동0(타지역 자동 처리) 제외, 2점 15 / 1점 15 / 0점 10
            1점·0점은 애매한 경계 사례(통합공고·위기·분야 한정·해외·여성 등)를 절반 이상 포함
            질문 하나에서 최대 3줄, 같은 공고는 최대 2줄, 순서는 섞어서 점수별로 몰리지 않게
"""
import re, shutil, tempfile
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HERE = Path(__file__).resolve().parent
SRC = HERE / "pool_snap1016.xlsx"
SEED = 1024
N = {2: 15, 1: 15, 0: 10}
BORDER = r"여성|통합|위기|폐업|LIPS|립스|해외|분야|한정|개업|크라우드|상담"

def read(sheet, **kw):
    try:
        return pd.read_excel(SRC, sheet_name=sheet, **kw)
    except PermissionError:                         # 엑셀에서 열려 있으면 복사본으로 읽기
        tmp = Path(tempfile.mkdtemp()) / "pool.xlsx"
        shutil.copy(SRC, tmp)
        return pd.read_excel(tmp, sheet_name=sheet, **kw)

pool = read("답안지")
rules = read("채점기준", header=None).dropna(how="all")
cand = pool[pool["할일"] != "자동0"].copy()
cand["경계"] = cand["점수이유"].fillna("").str.contains(BORDER) | cand["메모"].fillna("").astype(str).str.contains(BORDER)

picked, per_q, per_p = [], {}, {}
def take(df, n):
    out = []
    for _, r in df.sample(frac=1, random_state=SEED).iterrows():
        if len(out) == n: break
        if per_q.get(r.qid, 0) >= 3 or per_p.get(r.pblancId, 0) >= 2: continue
        per_q[r.qid] = per_q.get(r.qid, 0) + 1; per_p[r.pblancId] = per_p.get(r.pblancId, 0) + 1
        out.append(r)
    return out

for s, n in N.items():
    sub = cand[cand.score == s]
    border = take(sub[sub["경계"]], n // 2 + (n % 2) if s != 2 else 0)   # 2점은 경계 우선 안 함
    rest = take(sub[~sub.index.isin([r.name for r in border])], n - len(border))
    picked += border + rest

sel = pd.DataFrame(picked).sample(frac=1, random_state=SEED).reset_index(drop=True)
sel.insert(0, "번호", range(1, len(sel) + 1))

SHOW = ["번호", "qid", "질문", "공고명", "공고지역", "서울구", "지원대상", "분야", "사업개요", "URL"]
WIDTH = {"번호": 6, "qid": 6, "질문": 45, "공고명": 40, "공고지역": 8, "서울구": 10, "지원대상": 14,
         "분야": 14, "사업개요": 70, "URL": 20, "점수": 8, "이유": 35}
HEAD = PatternFill("solid", fgColor="DDEBF7"); INPUT = PatternFill("solid", fgColor="FFF2CC")

def sheet_table(ws, df, input_cols):
    cols = list(df.columns) + input_cols
    ws.append(cols)
    for r in df.itertuples(index=False): ws.append(list(r) + [None] * len(input_cols))
    for i, c in enumerate(cols, 1):
        cell = ws.cell(1, i); cell.font = Font(bold=True); cell.fill = INPUT if c in input_cols else HEAD
        key = next((k for k in WIDTH if k in c), None)
        ws.column_dimensions[cell.column_letter].width = WIDTH.get(key, 12)
        for row in range(2, len(df) + 2):
            ws.cell(row, i).alignment = Alignment(wrap_text=True, vertical="top")
            if c in input_cols: ws.cell(row, i).fill = INPUT
    ws.freeze_panes = "D2"

def rule_sheet(wb):
    ws = wb.create_sheet("채점기준")
    rows = rules.values.tolist()
    order = [r for r in rows if str(r[0]) in ("점수", "0", "1", "2")] + [[None, None]] + \
            [r for r in rows if re.fullmatch(r"[①-⑳]|규칙", str(r[0]))] + [[None, None]] + \
            [r for r in rows if str(r[0]) == "참고"]
    for r in order: ws.append(r)
    ws.column_dimensions["A"].width = 6; ws.column_dimensions["B"].width = 120
    for row in ws.iter_rows():
        for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")

def guide_sheet(wb, lines):
    ws = wb.active; ws.title = "안내"
    for l in lines: ws.append([l])
    ws.column_dimensions["A"].width = 110
    ws["A1"].font = Font(bold=True, size=13)

def score_validation(ws, col_letter, n):
    dv = DataValidation(type="list", formula1='"0,1,2"', allow_blank=True)
    ws.add_data_validation(dv); dv.add(f"{col_letter}2:{col_letter}{n + 1}")

# ── 1) 주희님용 (블라인드) ──
wb = Workbook()
guide_sheet(wb, [
    "교차 검증: 검색 정답지 40줄 채점 부탁드려요",
    "",
    "할 일: '채점' 시트의 노란 칸 2개만 채워주세요",
    "  · 주희_점수 : 0 / 1 / 2 중 하나 (칸을 누르면 목록이 나와요)",
    "  · 주희_이유 : 짧게 (애매했던 것만 적어도 돼요)",
    "",
    "점수의 뜻 (자세한 규칙은 '채점기준' 시트)",
    "  2 = 사용자가 원한 지원 그 자체",
    "  1 = 같은 종류지만 더 넓거나 조금 다름 / 사용자 상황과 관련된 지원",
    "  0 = 다른 종류, 또는 사용자가 직접 말한 정보와 충돌",
    "",
    "중요: 점수는 '이 질문과 관련 있나(관련도)'만 봐요. 신청 가능 여부(신호등)는 판정 단계라 여기선 안 봐요",
    "      예) 예비창업자 × 사업자등록이 필요한 공고 → 내용이 맞으면 1 이상 (판정에서 🟡)",
    "사업개요로 애매하면 URL에서 원문을 확인해주세요 (규칙 ⑪)",
    "",
    "다 하시면 이 파일 그대로 돌려주세요. 서로 점수가 다른 줄만 같이 이야기해서 규칙을 고쳐요",
])
ws = wb.create_sheet("채점")
sheet_table(ws, sel[SHOW], ["주희_점수", "주희_이유"])
score_validation(ws, ws.cell(1, len(SHOW) + 1).column_letter, len(sel))
rule_sheet(wb)
out1 = HERE / "교차검증_주희님용_40.xlsx"; wb.save(out1)

# ── 2) 내 보관용 (정답 포함) ──
wb = Workbook()
guide_sheet(wb, [
    "교차 검증 정답 비교 (김나애 보관용, 주희님께 보내지 않기)",
    "",
    "주희님 파일이 돌아오면 '주희_점수', '주희_이유'를 번호 순서대로 붙여넣기 → '일치' 칸이 자동 계산",
    "요약 시트: 완전 일치율, 0/1 vs 1/2 경계별 불일치 수",
    f"뽑은 방법: 자동0 제외, 2점 {N[2]} / 1점 {N[1]} / 0점 {N[0]}, 1·0점은 경계 사례 절반 이상, 질문당 최대 3줄, 공고당 최대 2줄 (seed {SEED})",
])
ws = wb.create_sheet("비교")
mine = sel[SHOW + ["score", "점수이유", "pblancId"]].rename(columns={"score": "나애_점수", "점수이유": "나애_이유"})
sheet_table(ws, mine, ["주희_점수", "주희_이유", "일치"])
c_mine = ws.cell(1, mine.columns.get_loc("나애_점수") + 1).column_letter
c_her = ws.cell(1, len(mine.columns) + 1).column_letter
c_eq = ws.cell(1, len(mine.columns) + 3).column_letter
for r in range(2, len(sel) + 2):
    ws[f"{c_eq}{r}"] = f'=IF({c_her}{r}="","",IF({c_her}{r}={c_mine}{r},"O","X"))'
s = wb.create_sheet("요약")
n = len(sel) + 1
s.append(["채점한 줄", f'=COUNT(비교!{c_her}2:{c_her}{n})'])
s.append(["완전 일치", f'=COUNTIF(비교!{c_eq}2:{c_eq}{n},"O")'])
s.append(["일치율", "=IFERROR(B2/B1,\"\")"])
s.append(["1점 이상 여부 일치 (정답/오답 기준)", f'=SUMPRODUCT((비교!{c_her}2:{c_her}{n}<>"")*((비교!{c_her}2:{c_her}{n}>=1)=(비교!{c_mine}2:{c_mine}{n}>=1)))'])
s.append(["정답 기준 일치율", "=IFERROR(B4/B1,\"\")"])
s["B3"].number_format = s["B5"].number_format = "0.0%"
s.column_dimensions["A"].width = 34
rule_sheet(wb)
out2 = HERE / "교차검증_정답비교_40.xlsx"; wb.save(out2)

print("저장:", out1.name, "/", out2.name)
print("점수 분포:", sel.score.value_counts().sort_index().to_dict(), "| 경계 사례:", int(sel["경계"].sum()),
      "| 질문 수:", sel.qid.nunique(), "| 공고 수:", sel.pblancId.nunique(), "| 공고지역:", sel["공고지역"].value_counts().to_dict())
print(sel[["번호", "qid", "score", "공고명", "점수이유"]].to_string(max_colwidth=40))
