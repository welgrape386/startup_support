"""
주희님 판정 정답지(교차검증_나애님용_40.xlsx)를 채점할 때 보는 참고 시트 만들기
- 판정은 하지 않음 (교차 검증이라 내 판단이어야 함). 계산·찾기만 대신 해줌
  · 사용자 입력에서 날짜를 찾아 기준일(2026-10-16) 기준 만 나이, 업력(개월) 계산
  · 공고 원문(texts_v8)에서 신청자격·지원대상 문단을 잘라서 붙임
- 입력: 카톡으로 받은 원본 (수정하지 않음)
- 출력: 교차검증_주희님정답_40_나애채점.xlsx (원본 복사 + '참고' 시트)
"""
import re, shutil
from datetime import date
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font

HERE = Path(__file__).resolve().parent
SRC = Path(r"C:\Users\USER\OneDrive - 성신여자대학교\문서\카카오톡 받은 파일\교차검증_나애님용_40.xlsx")
OUT = HERE / "교차검증_주희님정답_40_나애채점.xlsx"
TEXTS = HERE.parent / "01_원본" / "texts_v8_20261024" / "texts"
BASE = date(2026, 10, 16)
ELIG = re.compile(r"신청\s*자격|지원\s*대상|모집\s*대상|사업\s*대상|참여\s*대상|자격\s*요건|신청\s*대상|제외\s*대상|지원\s*제외|신청\s*제외")
DATE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일(생|에|부터)?\s*(\S*)")

def months(a, b):  # a → b 개월 수 (일 단위 반영)
    return (b.year - a.year) * 12 + b.month - a.month - (b.day < a.day)

def facts(text):
    out = []
    for m in DATE.finditer(text):
        d = date(*map(int, m.group(1, 2, 3)))
        ctx = text[m.start():m.end() + 25]
        if m.group(4) == "생":
            age = BASE.year - d.year - ((BASE.month, BASE.day) < (d.month, d.day))
            out.append(f"만 {age}세 (연나이 {BASE.year - d.year}세)")
        elif "폐업" in ctx:
            out.append(f"폐업일 {d} (폐업 후 {months(d, BASE)}개월)")
        else:
            out.append(f"창업일 {d} → 업력 {months(d, BASE)}개월 ({months(d, BASE) / 12:.1f}년)")
    return " / ".join(out) or "날짜 없음"

def elig_text(pid, limit=1800):
    f = TEXTS / f"{pid}.txt"
    if not f.exists(): return "(원문 없음, 사업개요·URL 확인)"
    lines = f.read_text(encoding="utf-8").splitlines()
    keep = set()
    for i, l in enumerate(lines):
        if ELIG.search(l): keep.update(range(i, min(i + 12, len(lines))))
    txt = "\n".join(lines[i].rstrip() for i in sorted(keep) if lines[i].strip())
    return (txt[:limit] + "\n…(이하 생략, 원문 확인)") if len(txt) > limit else (txt or "(자격 문단 못 찾음, 원문 확인)")

try:
    shutil.copy(SRC, OUT)
except PermissionError:   # 엑셀에서 열려 있으면 파이썬이 못 읽음 → 이미 복사해둔 OUT 사용
    if not OUT.exists(): raise SystemExit("원본 엑셀을 닫고 다시 실행하세요")
wb = load_workbook(OUT)
src = wb["채점"]
for old in [s for s in wb.sheetnames if s.startswith("참고")]: del wb[old]   # 다시 실행할 때 중복 방지
ws = wb.create_sheet("참고", 2)
ws.append(["번호", "사용자 입력", "사용자 계산값 (기준일 2026-10-16)", "공고명", "원문 자격 문단 (자동으로 잘라냄)"])
for r in src.iter_rows(min_row=2, values_only=True):
    if r[0] is None: continue
    pid = str(r[8]).split("pblancId=")[-1]
    ws.append([r[0], r[1], facts(r[1]), r[2], elig_text(pid)])
for col, w in zip("ABCDE", [6, 40, 30, 35, 100]): ws.column_dimensions[col].width = w
for row in ws.iter_rows():
    for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
for c in ws[1]: c.font = Font(bold=True)
ws.freeze_panes = "C2"
wb.save(OUT)
print("저장:", OUT.name)
for row in ws.iter_rows(min_row=2, max_row=41, values_only=True): print(row[0], "|", row[2])
