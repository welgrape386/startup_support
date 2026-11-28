"""
기업마당 공고 원문 다운로드 + 텍스트 추출

사용법 (내 컴퓨터에서 실행):
    pip install requests pymupdf olefile pandas
    python extract_texts.py bizinfo_1.csv

옵션:
    --all        서비스 범위 필터 없이 전체 공고 처리
    --limit N    앞에서 N건만 처리 (시험용)
    --out DIR    결과 폴더 (기본: ./output)

결과:
    output/files/{공고ID}.{확장자}   내려받은 원본 파일
    output/texts/{공고ID}.txt        추출한 텍스트 (김나애님 전달용)
    output/extract_report.csv        공고별 결과 (형식, 상태, 글자수, 오류)
    화면에 형식별 성공률 출력

다시 실행하면 이미 받은 파일은 건너뛴다 (중간에 끊겨도 이어서 가능).
"""

import argparse
import re
import struct
import sys
import time
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# 1. 서비스 범위 필터 (스키마 0절)
#    ① 지원대상이 소상공인·창업벤처
#    ② 공고명·사업개요·해시태그에 예비창업 관련 표현
#    ③ 공고명·사업개요에 초기창업 관련 표현, 또는 공고명에 "스타트업" (v5, 스키마 v0.1에서 초기창업자 추가)
#       해시태그만 걸린 공고와 사업개요에 "스타트업"이 지나가듯 나온 공고는 제외 (오탐이 많음)
# ---------------------------------------------------------------------------
TARGETS = {"소상공인", "창업벤처"}
PRE_STARTUP = re.compile(r"예비\s*창업|사업자\s*등록\s*(?:전|이전|前)|창업\s*예정|미창업|창업\s*희망")
EARLY_STARTUP = re.compile(r"초기\s*창업|창업\s*(?:후\s*)?\d+\s*년\s*(?:이내|미만|이하)|업력\s*\d+\s*년\s*(?:이내|미만|이하)|"
                           r"창업\s*기업|청년\s*창업|창업\s*\d+\s*년\s*차|팁스|TIPS|창업\s*(?:지원|육성)\s*자금")


def _text(row, cols) -> str:
    return " ".join(str(row.get(c)) for c in cols if pd.notna(row.get(c)))


def in_scope(row) -> bool:
    if str(row.get("trgetNm", "")).strip() in TARGETS:
        return True
    if PRE_STARTUP.search(_text(row, ("pblancNm", "bsnsSumryCn", "hashtags"))):
        return True
    return bool(EARLY_STARTUP.search(_text(row, ("pblancNm", "bsnsSumryCn"))) or "스타트업" in _text(row, ("pblancNm",)))


# ---------------------------------------------------------------------------
# 2. 공고문 파일 고르기
#    기본은 본문출력파일(printFile). 이름에 '공고'가 없고(예: 홍보물)
#    첨부파일 중 '공고'가 들어간 파일이 있으면 그걸 쓴다 (pdf > hwpx > hwp 순).
# ---------------------------------------------------------------------------
EXT_PRIORITY = {"pdf": 0, "hwpx": 1, "hwp": 2, "docx": 3}


def split_multi(value):
    if pd.isna(value) or not str(value).strip():
        return []
    return [v.strip() for v in str(value).split("@")]


def ext_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def pick_file(row):
    """(파일명, URL, 출처) 반환. 출처: 본문출력파일 / 첨부파일"""
    print_names = split_multi(row.get("printFileNm"))
    print_urls = split_multi(row.get("printFlpthNm"))
    main = (print_names[0], print_urls[0], "본문출력파일") if print_names and print_urls else None

    if main and "공고" in main[0]:
        return main

    att = list(zip(split_multi(row.get("fileNm")), split_multi(row.get("flpthNm"))))
    cands = [(n, u) for n, u in att if "공고" in n and ext_of(n) in EXT_PRIORITY]
    if cands:
        cands.sort(key=lambda x: EXT_PRIORITY[ext_of(x[0])])
        return cands[0][0], cands[0][1], "첨부파일"
    return main


def fallback_files(row, used_url):
    """고른 파일에서 텍스트를 못 얻었을 때 시도할 첨부파일 (이름에 '공고' + 문서 형식, pdf > hwpx > hwp 순)"""
    att = list(zip(split_multi(row.get("fileNm")), split_multi(row.get("flpthNm"))))
    cands = [(n, u) for n, u in att if u != used_url and "공고" in n and ext_of(n) in EXT_PRIORITY]
    cands.sort(key=lambda x: EXT_PRIORITY[ext_of(x[0])])
    return [(n, u, "첨부파일(재시도)") for n, u in cands]


# ---------------------------------------------------------------------------
# 3. 다운로드
# ---------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (research project; bizinfo text extraction)"


def download(url: str, dest: Path, retries: int = 2) -> None:
    last = None
    for attempt in range(retries + 1):
        try:
            r = SESSION.get(url, timeout=30)
            r.raise_for_status()
            if len(r.content) < 100:
                raise ValueError(f"파일이 너무 작음 ({len(r.content)} bytes)")
            dest.write_bytes(r.content)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"다운로드 실패: {last}")


# ---------------------------------------------------------------------------
# 4. 형식 판별 (확장자보다 실제 파일 내용 우선)
# ---------------------------------------------------------------------------
def detect_format(path: Path, declared: str) -> str:
    head = path.read_bytes()[:8]
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "hwp"
    if head.startswith(b"PK"):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                if any(n.startswith("Contents/section") for n in names):
                    return "hwpx"
                if "word/document.xml" in names:
                    return "docx"
            return "zip"
        except zipfile.BadZipFile:
            pass
    return declared or "unknown"


# ---------------------------------------------------------------------------
# 5. 텍스트 추출
# ---------------------------------------------------------------------------
MIN_CHARS = 200  # 이보다 짧으면 이미지 위주 문서로 본다

# 사람이 확인해서 추출 실패로 분류한 공고 (v8). 글자는 다 뽑히지만 왼쪽·오른쪽 내용이 한 줄에 섞여 읽기 어려움
# 자동으로 단을 나누면 다른 공고의 표·순서도가 깨져서(시험 결과) 코드로 고치지 않고 실패로 둔다
MANUAL_FAIL = {
    "PBLN_000000000120234": "2단 편집: 왼쪽 단(지원대상)과 오른쪽 단(제출서류)이 한 줄에 섞임",
    "PBLN_000000000119754": "한 장에 두 쪽 인쇄: 왼쪽 쪽과 오른쪽 쪽 내용이 한 줄에 섞임",
}

# PDF는 글자 하나하나의 좌표로 줄을 다시 조립한다 (v6)
#   - 같은 높이(기준선)의 글자를 한 줄로 모으고 왼쪽부터 놓는다
#     → 본문과 따로 저장된 쉼표·괄호가 제자리에 들어간다 (v5: "유흥업도박,  및" → v6: "유흥업, 도박 및")
#     → 떨어져 있던 숫자도 제자리에 들어간다 (v2에서 sort=True로 하던 일)
#   - 글자 사이 간격이 글자 폭 × PDF_GAP_SPACE보다 넓거나 PDF에 공백 글자가 있으면 띄어쓰기 (v2 규칙)
#     → 공백 글자 없이 위치만 띄운 PDF ("국세또는지방세체납으로…")
#   - 같은 글자가 폭·높이의 PDF_DUP_RATIO 안에 겹쳐 있으면 하나만 남긴다
#     → 글자 그림자·외곽선 효과로 같은 글자를 여러 번 그린 PDF ("202620262026…", "지원대상지원대상")
PDF_GAP_SPACE = 0.25   # 공백 1칸
PDF_GAP_COLUMN = 2.0   # 공백 2칸 (표·단 구분)
PDF_DUP_RATIO = 0.3
PDF_LINE_RATIO = 0.5   # 기준선 차이가 글자 높이의 50% 이내면 같은 줄


# Wingdings 글꼴: 기호를 알파벳 자리에 넣어 둔 글꼴이라 텍스트로는 "m"(❍), "§"(▪) 같은 글자가 나온다 (v7)
# 글자 코드(cp1252 바이트) → 화면에 보이는 기호. 표에 없는 코드는 □ (PUA 처리와 같은 방식)
WINGDINGS = {
    0x28: "☎", 0x2A: "✉", 0x46: "☞",
    0x6C: "●", 0x6D: "❍", 0x6E: "■", 0x6F: "□", 0x70: "□", 0x71: "❑", 0x72: "❒",
    0x73: "⬧", 0x74: "⧫", 0x75: "◆", 0x76: "❖", 0x77: "⬥", 0x78: "⌧",
    **{0x80 + i: chr(0x24EA) if i == 0 else chr(0x2460 + i - 1) for i in range(10)},  # ⓪ ①~⑨
    0x8A: "⓿", **{0x8B + i: chr(0x2776 + i) for i in range(10)},                    # ❶~❿
    0x9E: "·", 0x9F: "•", 0xA1: "○", 0xA7: "▪",
    0xD8: "➢", 0xDB: "◀", 0xDC: "▶", 0xDD: "▲", 0xDE: "▼",
    0xE7: "⬅", 0xE8: "➔", 0xE9: "⬆", 0xEA: "⬇", 0xEF: "⇦", 0xF0: "⇨", 0xF1: "⇧", 0xF2: "⇩",
    0xFB: "✗", 0xFC: "✔", 0xFD: "☒", 0xFE: "☑",
}


def _wingdings(ch: str) -> str:
    if not ch.strip():
        return ch
    try:
        code = ch.encode("cp1252")[0]
    except UnicodeEncodeError:
        code = ord(ch)
    return WINGDINGS.get(code, "□")


def _pdf_chars(page):
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                wing = "wingdings" in s["font"].lower()
                for c in s["chars"]:
                    x0, y0, x1, y1 = c["bbox"]
                    if wing:
                        ch = _wingdings(c["c"])  # 제어문자도 Wingdings에서는 기호 자리 → □
                    else:
                        ch = " " if ord(c["c"][:1] or " ") < 32 else c["c"]  # 제어문자(\x01 등)를 공백으로 쓰는 PDF가 있음
                    out.append({"c": ch, "x": c["origin"][0], "y": c["origin"][1], "x1": x1,
                                "w": max(x1 - x0, 0.1), "h": max(y1 - y0, s["size"] * 0.8, 0.1)})
    return out


def _pdf_dedupe(chars):
    kept, grid = [], {}
    for c in chars:
        if c["c"].strip():
            gx, gy = round(c["x"] / 4), round(c["y"] / 4)
            near = [o for dx in (-1, 0, 1) for dy in (-1, 0, 1) for o in grid.get((c["c"], gx + dx, gy + dy), [])]
            if any(abs(o["x"] - c["x"]) < PDF_DUP_RATIO * c["w"] and abs(o["y"] - c["y"]) < PDF_DUP_RATIO * c["h"] for o in near):
                continue
            grid.setdefault((c["c"], gx, gy), []).append(c)
        kept.append(c)
    return kept


def _pdf_page_text(chars) -> str:
    lines = []
    for c in sorted(chars, key=lambda c: (c["y"], c["x"])):
        if lines and abs(c["y"] - lines[-1]["y"]) <= PDF_LINE_RATIO * max(c["h"], lines[-1]["h"]):
            lines[-1]["chars"].append(c)
        else:
            lines.append({"y": c["y"], "h": c["h"], "chars": [c]})
    out, prev_y = [], None
    for ln in lines:
        cs = sorted(ln["chars"], key=lambda c: c["x"])
        widths = sorted(c["w"] for c in cs if c["c"].strip())
        if not widths:
            continue
        w = widths[len(widths) // 2]
        text, prev, saw_space = [], None, False
        for c in cs:
            if not c["c"].strip():
                saw_space = prev is not None
                continue
            if prev is not None:
                gap = c["x"] - prev["x1"]
                if gap > PDF_GAP_COLUMN * w:
                    text.append("  ")
                elif gap > PDF_GAP_SPACE * w or saw_space:
                    text.append(" ")
            text.append(c["c"])
            prev, saw_space = c, False
        if prev_y is not None and ln["y"] - prev_y > 2.2 * ln["h"]:
            out.append("")  # 문단 간격
        out.append("".join(text))
        prev_y = ln["y"]
    return "\n".join(out)


def extract_pdf(path: Path) -> str:
    import pymupdf

    pymupdf.TOOLS.mupdf_display_errors(False)  # 깨진 PDF 구조 자동복구 경고 (추출에는 영향 없음)
    with pymupdf.open(path) as doc:
        return "\n".join(_pdf_page_text(_pdf_dedupe(_pdf_chars(page))) for page in doc)


# 일부 누락 의심: 강조된 글자를 그림(윤곽선)으로 저장한 PDF는 그 글자가 빠지고 문장부호만 남는다
#   예) "① 온라인 : 행복카드.kr" → "①  :  .kr", "- 읍, 면, 동 행정복지센터" → "-  ,  ,"
#   한글이 하나도 없이 홀로 남은 쉼표·콜론이 있는 줄이 2개 이상이면 표시 (OCR 대상 후보)
_HOLLOW = re.compile(r"(?:^|\s)[,:](?=\s|$)|\(\s*(?:,\s*)+\)")


def partial_missing(text: str) -> bool:
    return sum(1 for l in text.splitlines() if l.strip() and not re.search(r"[가-힣]", l) and _HOLLOW.search(l)) >= 2


def extract_hwpx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        sections = sorted(
            (n for n in z.namelist() if re.match(r"Contents/section\d+\.xml$", n)),
            key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[-1]).group(1)),
        )
        parts = []
        for name in sections:
            root = ET.fromstring(z.read(name))
            for el in root.iter():
                tag = el.tag.rsplit("}", 1)[-1]
                if tag == "p":
                    parts.append("\n")
                elif tag == "t":
                    parts.append("".join(el.itertext()))
        return "".join(parts)


# HWP5 문단 텍스트 안의 제어문자: 이 코드들은 8글자(16바이트)를 차지한다
HWP_WIDE_CTRL = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
HWPTAG_PARA_TEXT = 67


def _hwp_para_text(data: bytes) -> str:
    out, i, n = [], 0, len(data) // 2
    while i < n:
        code = struct.unpack_from("<H", data, i * 2)[0]
        if code in HWP_WIDE_CTRL:
            if code == 9:
                out.append("\t")
            i += 8
            continue
        if code in (10, 13):
            out.append("\n")
        elif code >= 32:
            out.append(chr(code))
        i += 1
    return "".join(out)


def extract_hwp(path: Path) -> str:
    import olefile

    with olefile.OleFileIO(str(path)) as ole:
        header = ole.openstream("FileHeader").read()
        flags = struct.unpack_from("<I", header, 36)[0]
        compressed, encrypted, distribution = flags & 1, flags & 2, flags & 4
        if encrypted:
            raise ValueError("암호화된 HWP")
        if distribution or not ole.exists("BodyText/Section0"):
            raise ValueError("배포용 HWP (텍스트 추출 불가)")

        sections = sorted(
            (e for e in ole.listdir() if len(e) == 2 and e[0] == "BodyText" and e[1].startswith("Section")),
            key=lambda e: int(e[1][7:]),
        )
        parts = []
        for entry in sections:
            raw = ole.openstream(entry).read()
            data = zlib.decompress(raw, -15) if compressed else raw
            pos = 0
            while pos + 4 <= len(data):
                h = struct.unpack_from("<I", data, pos)[0]
                tag, size = h & 0x3FF, (h >> 20) & 0xFFF
                pos += 4
                if size == 0xFFF:
                    size = struct.unpack_from("<I", data, pos)[0]
                    pos += 4
                if tag == HWPTAG_PARA_TEXT:
                    parts.append(_hwp_para_text(data[pos : pos + size]))
                pos += size
        # 2바이트씩 chr()로 읽어서 4바이트 글자(한컴 기호 등)가 서로게이트 두 개로 쪼개져 있음 → 한 글자로 합친다
        text = "".join(parts)
        return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


def extract_docx(path: Path) -> str:
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    parts = []
    for el in root.iter():
        if el.tag == w + "p":
            parts.append("\n")
        elif el.tag == w + "t":
            parts.append(el.text or "")
        elif el.tag == w + "tab":
            parts.append("\t")
        elif el.tag == w + "br":
            parts.append("\n")
    return "".join(parts)


EXTRACTORS = {"pdf": extract_pdf, "hwpx": extract_hwpx, "hwp": extract_hwp, "docx": extract_docx}

# 한글/기호 글꼴의 사용자 정의 영역(PUA) 문자 정리
# U+F081~F08A: 원문자 ①~⑩ (127211 공고 제출서류 목록에서 확인), U+F0A0: 공백, 나머지: 글머리 기호로 보고 □
PUA = re.compile("[-\U000f0000-\U0010fffd]")
PUA_MAP = {**{chr(0xF081 + i): chr(0x2460 + i) for i in range(10)}, "": " "}


def clean_text(text: str) -> str:
    text = PUA.sub(lambda m: PUA_MAP.get(m.group(), "□"), text)
    # 공백 정리 (PDF sort=True가 표 칸 맞춤용 공백을 많이 넣음 → 토큰 낭비)
    text = re.sub(r"[ \t]{3,}", "  ", text)        # 3칸 이상 공백 → 2칸 (칸 구분은 남김)
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)  # 줄 끝 공백
    return re.sub(r"\n{3,}", "\n\n", text)           # 빈 줄 2개 이상 → 1개


# ---------------------------------------------------------------------------
# 6. 실행
# ---------------------------------------------------------------------------
def try_file(pid, picked, files_dir: Path, suffix: str = "") -> dict:
    """파일 하나를 받아 텍스트 추출. 리포트 칸 + text(추출 못 하면 None) 반환"""
    name, url, source = picked
    declared = ext_of(name)
    res = {"파일명": name, "파일출처": source, "형식": declared, "상태": None, "글자수": 0, "일부누락의심": False,
           "오류": None, "text": None}
    dest = files_dir / f"{pid}{suffix}.{declared or 'bin'}"
    try:
        if not dest.exists():
            download(url, dest)
            time.sleep(0.5)  # 서버 부담 줄이기
        fmt = detect_format(dest, declared)
        res["형식"] = fmt
        if fmt not in EXTRACTORS:
            raise ValueError(f"지원하지 않는 형식: {fmt}")
        text = clean_text(EXTRACTORS[fmt](dest))
        res["text"], res["글자수"] = text, len(text.strip())
        res["일부누락의심"] = fmt == "pdf" and partial_missing(text)  # hwp 서식의 빈 칸("FAX : ")은 누락이 아님
        res["상태"] = "성공" if res["글자수"] >= MIN_CHARS else "텍스트거의없음(이미지추정)"
    except RuntimeError as e:
        res["상태"], res["오류"] = "다운로드실패", str(e)[:200]
    except Exception as e:  # noqa: BLE001
        res["상태"], res["오류"] = "추출실패", f"{type(e).__name__}: {e}"[:200]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--all", action="store_true", help="서비스 범위 필터 없이 전체 처리")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    df = pd.read_csv(args.csv, encoding="utf-8-sig")
    if not args.all:
        df = df[df.apply(in_scope, axis=1)]
    if args.limit:
        df = df.head(args.limit)

    out = Path(args.out)
    files_dir, texts_dir = out / "files", out / "texts"
    files_dir.mkdir(parents=True, exist_ok=True)
    texts_dir.mkdir(parents=True, exist_ok=True)

    print(f"처리 대상: {len(df)}건")
    rows = []
    for i, (_, row) in enumerate(df.iterrows(), 1):
        pid = row["pblancId"]
        rec = {
            "공고ID": pid,
            "공고명": row.get("pblancNm"),
            "지원대상": row.get("trgetNm"),
            "파일명": None,
            "파일출처": None,
            "형식": None,
            "상태": None,
            "글자수": 0,
            "오류": None,
            "일부누락의심": False,  # 글자가 그림으로 저장돼 일부가 빠진 것으로 보임 (OCR 후보)
            "1차결과": None,  # 재시도했거나 최종 실패한 경우, 처음 고른 파일의 "형식:상태"
        }
        picked = pick_file(row)
        if not picked:
            rec["상태"] = "파일없음"
            rows.append(rec)
            continue

        res = try_file(pid, picked, files_dir)
        first = f"{res['형식']}:{res['상태']}"
        # 고른 파일에서 텍스트를 못 얻으면 첨부파일 중 '공고' 문서로 재시도 (예: 공고문이 이미지 PDF, hwp 공고문은 첨부)
        if res["상태"] != "성공":
            for k, fb in enumerate(fallback_files(row, picked[1]), 1):
                res2 = try_file(pid, fb, files_dir, suffix=f"_att{k}")
                if res2["상태"] == "성공":
                    res = res2
                    break
        if res["상태"] != "성공" or res["파일출처"] == "첨부파일(재시도)":
            res["1차결과"] = first
        text = res.pop("text")
        if text is not None:
            (texts_dir / f"{pid}.txt").write_text(text, encoding="utf-8")
        rec.update(res)
        if rec["상태"] == "성공" and pid in MANUAL_FAIL:   # 사람이 확인해서 실패로 분류한 공고 (텍스트 파일은 남김)
            rec["상태"], rec["오류"] = "추출실패(2단편집)", MANUAL_FAIL[pid]
        rows.append(rec)
        print(f"[{i}/{len(df)}] {pid} {rec['형식']} → {rec['상태']} ({rec['글자수']}자)")

    report = pd.DataFrame(rows)
    report.to_csv(out / "extract_report.csv", index=False, encoding="utf-8-sig")

    # 형식별 성공률
    print("\n=== 형식별 성공률 ===")
    summary = (
        report.assign(성공=report["상태"].eq("성공"))
        .groupby("형식", dropna=False)
        .agg(대상=("공고ID", "count"), 성공=("성공", "sum"))
    )
    summary["성공률"] = (summary["성공"] / summary["대상"]).round(3)
    print(summary.to_string())
    total_ok = int(report["상태"].eq("성공").sum())
    print(f"\n전체: {total_ok}/{len(report)} ({total_ok / max(len(report), 1):.1%})")
    print("\n상태별 건수:")
    print(report["상태"].value_counts().to_string())
    partial = report[report["상태"].eq("성공") & report["일부누락의심"]]["공고ID"].tolist()
    print(f"\n일부누락의심 (성공 중 글자가 그림으로 빠진 것으로 보이는 공고): {len(partial)}건 {partial}")
    summary.to_csv(out / "format_success_rate.csv", encoding="utf-8-sig")


if __name__ == "__main__":
    sys.exit(main())
