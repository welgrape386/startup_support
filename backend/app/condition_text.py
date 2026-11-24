# 조건 문구 함수 ([조건] 만들기)
# 판정에서 노란불/확인필요 나온 조건 -> 카드에 보여줄 [조건] 문구로 바꿈
# 신호등이 노란불일 때만 부름. 판정은 안 함
#
# make_condition_text(공고JSON, {"지역": Y, "업력": Q}, stage="예비")
# -> ["서대문구에서 창업하면 신청 가능", "개업일 2025년 7월 1일 이전 확인 필요"]
#
# 판정 결과 그대로 넣을 땐 from_judgment (맨 아래)
# -> {"pblancId", "signal", "condition_texts"} 백엔드로 넘길 값

import json
import re

Y = "🟡"   # 조건 결과: 노란불 (조건부)
Q = "❔"   # 조건 결과: 확인 필요

ORDER = ["나이", "지역", "사업자등록", "업력", "업종", "신청자_유형", "성별", "특수자격", "대안조건"]
LABEL = {"신청자_유형": "신청자 유형", "특수자격": "대상 자격", "대안조건": "대안 조건"}
BIZ_PLACE = {"사업장소재지", "사업자등록지", "본사소재지"}
CAREER_BASE = {"개업일": "개업일", "법인설립등기일": "법인 설립일"}


def _join(xs):
    return ", ".join(str(x) for x in xs if x)


def _short(text, n=40):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n] + "…"


def _few(xs, n=3):
    # 앞 3개만 · 로 잇고 나머지는 "외 n개"
    xs = [str(x) for x in xs if x]
    return "·".join(xs[:n]) + (f" 외 {len(xs) - n}개" if len(xs) > n else "")


def _ro(word):
    # 받침 있으면 "으로", 없거나 ㄹ이면 "로"
    c = word[-1]
    if not "가" <= c <= "힣":
        return "로"
    jong = (ord(c) - 0xAC00) % 28
    return "으로" if jong and jong != 8 else "로"


def _months(m):
    m = int(m)
    return f"{m // 12}년" if m % 12 == 0 else f"{m}개월"


def _date(s):
    y, m, d = str(s).split("-")
    return f"{y}년 {int(m)}월 {int(d)}일"


def _clip(text, n=60):
    # 괄호, 뒷문장 떼고 앞부분만
    text = re.sub(r"\s*\([^)]*\)", "", " ".join(str(text or "").split()))
    text = re.split(r"\. |, 또는 ", text)[0]
    return _short(text, n)


def _unknown(name, part):
    # 템플릿 없을 때 -> "{조건} 확인 필요 (원문 앞부분)"
    why = _short(part.get("근거")) if isinstance(part, dict) and name != "업력" else ""   # 업력 원문은 어색해서 안 붙임
    return f"{LABEL.get(name, name)} 확인 필요" + (f" ({why})" if why else "")


# 조건별 문구 ----------------------------------------------------------------
def _region(p, stage):
    gu = _join(r.get("시군구") or r.get("시도") for r in (p.get("범위") or []))
    kinds = set(p.get("유형") or [])
    if not gu:
        return None
    if stage in ("예비", "예비창업") and kinds & BIZ_PLACE:
        return f"{gu}에서 창업하면 신청 가능"
    if kinds & {"거주지", "주민등록지"}:
        return f"{gu} 거주 조건 확인 필요"
    return f"{gu} 소재 사업장만 신청 가능"


def _biz(p, stage):
    # 사업자등록 노란불은 선정 후 등록하면 되는 경우뿐 (JSON 값이 "불가"여도 판정이 노란불 줌)
    return "선정 후 사업자등록 필요"


def _career(p, stage):
    # 날짜 있으면 날짜로, 없으면 개월 수로 (개업일 안 적어서 확인필요인 경우)
    who = CAREER_BASE.get(p.get("업력_기준"), "창업일")
    r = p.get("창업일_범위") or {}
    try:
        if r.get("to"):
            return f"{who} {_date(r['to'])} {r.get('to_경계') or '이전'} 확인 필요"
        if r.get("from"):
            return f"{who} {_date(r['from'])} {r.get('from_경계') or '이후'} 확인 필요"
    except ValueError:   # 날짜 모양 다르면 개월 수로
        pass
    lo, hi = p.get("min_개월"), p.get("max_개월")
    if lo and hi:
        return f"업력 {_months(lo)} 이상 {_months(hi)} 이내 확인 필요"
    if lo:
        return f"업력 {_months(lo)} 이상 확인 필요"
    if hi:
        return f"업력 {_months(hi)} {'미만' if p.get('경계_max') == '미만' else '이내'} 확인 필요"
    return None


def _industry(p, stage):
    names = p.get("업종명") or {}
    allow, deny = names.get("허용") or [], names.get("제외") or []
    if allow:
        text = _few(allow)
        if not re.search(r"(분야|업종|전반|기업|[^창]업)$", text):   # 제조업, 생활밀접업종은 "분야" 안 붙임
            text += " 분야"
        return f"{text}{_ro(text)} 창업하면 신청 가능"
    if deny:
        if len(deny) > 3:
            return f"{'·'.join(map(str, deny[:3]))} 등 {len(deny)}개 업종 외로 창업하면 신청 가능"
        return f"{_few(deny)} 외 업종으로 창업하면 신청 가능"
    if p.get("제외_참조"):   # 소상공인정책자금_융자제외 같은 기준 이름만 있는 경우
        return f"{str(p['제외_참조']).replace('_', ' ')} 업종이 아니면 신청 가능"
    return None


def _applicant(p, stage):
    vals = p.get("값") or []
    return f"{vals[0]}만 신청 가능" if len(vals) == 1 else None


def _gender(p, stage):
    return f"{p['값']} 대표자만 신청 가능" if p.get("값") else None


def _special(items, stage):
    names = [it.get("값") or it.get("이름") or it.get("유형") or it.get("내용") if isinstance(it, dict) else it
             for it in items or []]
    return f"{_join(names)}만 신청 가능" if any(names) else None


def _alternative(items, stage):
    descs = [_short(it.get("설명"), 60) for it in (items or []) if isinstance(it, dict) and it.get("설명")]
    return " / ".join(f"{d}이면 신청 가능" for d in descs) or None


def _age(p, stage):
    lo, hi = p.get("min"), p.get("max")
    if lo is None and hi is None:
        return None
    lo, hi = (int(x) if isinstance(x, float) else x for x in (lo, hi))
    if lo is not None and hi is not None:
        rng = f"만 {lo}~{hi}세"
    else:
        rng = f"만 {lo}세 이상" if lo is not None else f"만 {hi}세 이하"
    who = p.get("대상")
    if who and who not in ("대표자", "신청자_본인", "구성원_전원"):
        return f"{who.replace('_', ' ')} {rng} 조건 확인 필요"   # 채용 직원 나이 같은 경우
    return f"{rng}만 신청 가능"


RULES = {"지역": _region, "사업자등록": _biz, "업력": _career, "업종": _industry,
         "신청자_유형": _applicant, "성별": _gender, "특수자격": _special, "대안조건": _alternative, "나이": _age}
Q_RULES = {"업력": _career}   # 확인필요여도 템플릿 쓰는 조건


# 사용자 맞춤 문구 -----------------------------------------------------------
def _choice(c):
    # 대안조건 선택지 하나 -> 짧은 말 (예: 재해중소기업 확인증 또는 피해사실확인서 보유 기업)
    parts = []
    for k, v in (c or {}).items():
        v = v or {}
        if k == "특수자격":
            parts += [x.get("값") if isinstance(x, dict) else x for x in (v if isinstance(v, list) else [v])]
        elif k == "보유요건":
            what = _clip(v.get("내용"))
            if v.get("종류") == "매출실적":
                parts.append(what)
            elif what:
                parts.append(f"{what} 보유 기업")
            elif v.get("종류"):
                parts.append(str(v["종류"]).replace("확인", ""))   # 벤처기업확인 -> 벤처기업
        elif k == "업력":
            lo, hi = v.get("min_개월"), v.get("max_개월")
            parts.append(f"업력 {_months(lo)} 이상" if lo else (f"업력 {_months(hi)} 이내" if hi else "업력 기준 이내"))   # 기간 안 적힌 것도 선택지로 남김
        elif k == "나이":
            lo, hi = v.get("min"), v.get("max")
            parts.append(f"만 {hi}세 이하" if hi else (f"만 {lo}세 이상" if lo else None))
        elif k == "기타조건":
            parts.append(_clip(v.get("내용")))
        elif k == "기업규모":
            parts.append(v.get("구분"))
    return ", ".join(str(x) for x in parts if x)


def _alternative_left(items, left):
    # 남은 선택지 번호로만 문구 만듦 (대안조건 묶음은 62건 다 하나)
    group = items[0] if isinstance(items, list) and items else {}
    choices = group.get("선택지") or []
    words = [_choice(choices[i]) for i in left if isinstance(i, int) and 0 <= i < len(choices)]
    words = [w for w in words if w]
    return " 또는 ".join(words) + "이면 신청 가능" if words else None


def _picked(name, part, vals):
    # 판정이 골라준 값만 씀
    vals = [str(v) for v in vals if v]
    if not vals:
        return None
    if name == "업종":
        key = "허용" if (part.get("업종명") or {}).get("허용") else "제외"
        return _industry({"업종명": {key: vals}}, "")
    if name == "대안조건":
        return " 또는 ".join(vals) + "이면 신청 가능"
    return None


def _with_track(notice, track):
    # 트랙 조건을 공고 조건 위에 덮어씀 (트랙에 값 있는 칸만)
    for t in notice.get("트랙") or []:
        if track and t.get("이름") == track:
            merged = dict(notice)
            for k, v in (t.get("조건") or {}).items():
                if v and not (isinstance(v, dict) and v.get("상태") == "없음"):
                    merged[k] = v
            return merged
    return notice


def make_condition_text(notice, conds, stage="", picked=None, industry_reason=None, alt_left=None, track=None):
    # notice: 예은님 조건 JSON 한 공고 / conds: {조건 이름: Y 또는 Q} / stage: 예비, 개업
    # 아래는 있으면 사용자 맞춤으로 짧게, 없으면 공고에 적힌 거 다 씀
    # picked: {"업종": [...]} / industry_reason: 허용불일치, 제외 / alt_left: 남은 선택지 번호 / track: 트랙 이름
    picked = picked or {}
    notice = _with_track(notice, track)
    out = []
    for name in sorted(conds, key=lambda k: ORDER.index(k) if k in ORDER else len(ORDER)):
        part = notice.get(name) or {}
        mark = conds[name]
        text = None
        if mark == Y:
            if name == "업종" and industry_reason == "제외" and picked.get("업종"):
                text = _industry({"업종명": {"제외": picked["업종"]}}, stage)
            elif name == "업종" and industry_reason == "허용불일치":
                allow = picked.get("업종") or (part.get("업종명") or {}).get("허용") or []
                text = _industry({"업종명": {"허용": allow}}, stage) if allow else None
            elif name == "대안조건" and alt_left:
                text = _alternative_left(part, alt_left)
            elif name in picked:
                text = _picked(name, part, picked[name])
            if not text and name in RULES:
                text = RULES[name](part, stage)
        elif mark == Q and name == "대안조건" and alt_left:   # 판정은 대안조건을 ❔로 줌
            text = _alternative_left(part, alt_left)
        elif mark == Q and name in Q_RULES:
            text = Q_RULES[name](part, stage)
        out.append(text or _unknown(name, part))
    return out


# 판정 결과 연결 --------------------------------------------------------------
# 주희님 판정 결과 필드명. 다르면 오른쪽만 바꾸면 됨!!
FIELDS = {
    "pblancId":        "pblancId",
    "signal":          "signal",
    "stage":           "stage",
    "results":         "results",          # {조건 이름: 결과}
    "track":           "track",
    "industry_reason": "industry_reason",  # 허용불일치 / 제외
    "industry_hit":    "industry_hit",     # 걸린 제외 업종
    "alt_left":        "alt_left",         # 남은 대안조건 선택지 번호
}
COND_NAMES = {}   # 판정 쪽 조건 이름이 예은님 JSON이랑 다르면 여기 (예: {"신청자유형": "신청자_유형"})
Y_WORDS = (Y, "조건부")   # 기호 대신 글자로 와도 알아봄
Q_WORDS = (Q, "확인 필요", "확인필요", "모름")


def _has(value, words):
    return any(w in str(value or "") for w in words)


def load_notices(path):
    # 예은님 조건 JSON -> {공고ID: 공고}
    with open(path, encoding="utf-8") as f:
        return {d["공고ID"]: d for d in json.load(f)}


def from_judgment(result, notices, fields=None):
    # 판정 결과 하나(사용자 x 공고) -> 백엔드로 넘길 값. 노란불 아니면 condition_texts는 []
    f = {**FIELDS, **(fields or {})}
    get = lambda k: result.get(f[k])
    pid, signal = get("pblancId"), get("signal")
    out = {"pblancId": pid, "signal": signal, "condition_texts": []}
    if not _has(signal, Y_WORDS) or pid not in notices:
        return out
    conds = {}
    for name, v in (get("results") or {}).items():
        if _has(v, Y_WORDS):
            conds[COND_NAMES.get(name, name)] = Y
        elif _has(v, Q_WORDS):
            conds[COND_NAMES.get(name, name)] = Q
    hit = get("industry_hit")
    out["condition_texts"] = make_condition_text(
        notices[pid], conds, get("stage") or "", picked={"업종": hit} if hit else None,
        industry_reason=get("industry_reason"), alt_left=get("alt_left"), track=get("track"))
    return out
