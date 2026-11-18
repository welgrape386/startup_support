"""B1: LLM 직접 판정 (기준선)

공고 원문과 사용자 정보를 LLM에 주고 신호등(🟢/🟡/⚪/🔴)을 바로 판정하게 한다.

모델 기본값은 gpt-6.1-terra. 다른 모델은 --model 로 지정
"""
import argparse
import csv
import json
import os
import time
from collections import Counter

from dotenv import load_dotenv
from openai import OpenAI

# 개발 공고 15건 (나머지 15건은 평가)
DEV_IDS = {f'PBLN_000000000{n}' for n in (
    118108, 119567, 119739, 121175, 127031, 121480, 123795, 123842,
    123844, 124045, 125511, 126686, 126872, 126969, 127098)}

# 1M 토큰당 USD: (입력, 캐시 입력, 출력)
PRICES = {
    'gpt-6.1-sol': (2.00, 0.10, 10.00),
    'gpt-6.1-terra': (1.00, 0.05, 5.00),
}

LABELS = {'🟢': '🟢 신청 가능', '🟡': '🟡 조건부가능', '⚪': '⚪️ 확인 필요', '🔴': '🔴 신청 불가'}
COLUMNS = ['사용자', '공고ID', '예측', '근거 문장', '사유', '트랙', '조건별', '체크리스트', '오류']


def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def emoji(label):
    """'⚪️ 확인 필요' → '⚪'"""
    e = (label or '').strip().replace('\ufe0f', '')[:1]
    return e if e in LABELS else ''


def load_system_prompt(path):
    """md 파일에서 '## 시스템 프롬프트'와 '## 사용자 메시지 형식' 사이만 쓴다."""
    text = open(path, encoding='utf-8').read()
    start = text.index('## 시스템 프롬프트') + len('## 시스템 프롬프트')
    end = text.index('## 사용자 메시지 형식')
    return text[start:end].strip().removesuffix('---').strip()


def user_message(pid, text, user):
    """원문을 앞에, 사용자 정보를 뒤에 둔다. 같은 공고를 연달아 부르면 앞부분이 캐시된다."""
    info = {}
    for k, v in user.items():
        v = (v or '').strip()
        if v in ('', 'null'):
            v = None
        elif v[0] in '{[':
            v = json.loads(v)
        elif v.isdigit():
            v = int(v)
        info[k] = v
    return (f'[공고ID] {pid}\n\n[공고 원문]\n{text}\n\n'
            f'[사용자 정보]\n{json.dumps(info, ensure_ascii=False)}')


def judge(client, model, system, msg, tries=3):
    """한 쌍을 판정한다. 반환: (응답 dict 또는 None, usage, 오류 메시지)"""
    err = ''
    for i in range(tries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': msg}],
                response_format={'type': 'json_object'})
            data = json.loads(resp.choices[0].message.content)
            if not emoji(data.get('신호등')):
                raise ValueError(f'신호등 값 이상: {data.get("신호등")!r}')
            return data, resp.usage, ''
        except Exception as ex:
            err = f'{type(ex).__name__}: {ex}'
            time.sleep(2 ** i)
    return None, None, err


def to_row(g, data, err):
    row = {'사용자': g['사용자'], '공고ID': g['공고ID'], '오류': err}
    if data:
        text = lambda v: ' / '.join(map(str, v)) if isinstance(v, list) else str(v or '')
        row.update({
            '예측': LABELS[emoji(data['신호등'])],
            '근거 문장': text(data.get('근거 문장')),
            '사유': text(data.get('사유')),
            '트랙': text(data.get('트랙')),
            '조건별': json.dumps(data.get('조건별', []), ensure_ascii=False),
            '체크리스트': json.dumps(data.get('체크리스트', []), ensure_ascii=False),
        })
    return row


def metrics(pairs):
    """pairs: [(정답, 예측)] 이모지. 판정 실패한 예측은 ''로 들어와 오답이 된다."""
    green = [g for g, p in pairs if p == '🟢']
    per_class = {}
    for c in LABELS:
        tp = sum(g == c and p == c for g, p in pairs)
        pred = sum(p == c for _, p in pairs)
        gold = sum(g == c for g, _ in pairs)
        prec = tp / pred if pred else 0
        rec = tp / gold if gold else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        per_class[c] = {'P': round(prec, 3), 'R': round(rec, 3), 'F1': round(f1, 3)}
    return {
        '쌍 수': len(pairs),
        'Accuracy': round(sum(g == p for g, p in pairs) / len(pairs), 3),
        'False green': round(sum(g != '🟢' for g in green) / len(green), 3) if green else 0,
        '🟢 예측 수': len(green),
        'Macro-F1': round(sum(v['F1'] for v in per_class.values()) / 4, 3),
        '클래스별': per_class,
        '혼동행렬(정답→예측)': {g: dict(Counter(p or '실패' for gg, p in pairs if gg == g)) for g in LABELS},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--gold', required=True)
    ap.add_argument('--users', required=True)
    ap.add_argument('--texts', required=True, help='{공고ID}.txt 원문 폴더')
    ap.add_argument('--out', required=True)
    ap.add_argument('--model', default='gpt-6.1-terra')     # 시범 15쌍으로 모델 확정
    ap.add_argument('--pairs', help='사용자,공고ID csv. 이 쌍만 판정')
    ap.add_argument('--split', choices=['dev', 'eval'], help='개발/평가 공고만 판정')
    a = ap.parse_args()

    load_dotenv()
    client = OpenAI()
    system = load_system_prompt(a.prompt)
    users = {u['사용자ID']: u for u in read_csv(a.users)}

    rows = read_csv(a.gold)
    if a.split:
        rows = [g for g in rows if (g['공고ID'] in DEV_IDS) == (a.split == 'dev')]
    if a.pairs:
        want = {(p['사용자'], p['공고ID']) for p in read_csv(a.pairs)}
        rows = [g for g in rows if (g['사용자'], g['공고ID']) in want]
        if len(rows) != len(want):
            print(f'주의: --pairs {len(want)}쌍 중 {len(want) - len(rows)}쌍이 정답 파일에 없어 뺐어요')
    rows.sort(key=lambda g: (g['공고ID'], g['사용자']))
    if not rows:
        raise SystemExit('판정할 쌍이 없어요.')

    # API를 부르기 전에 원문 파일과 사용자가 다 있는지 확인
    texts = {}
    for pid in {g['공고ID'] for g in rows}:
        path = os.path.join(a.texts, pid + '.txt')
        if not os.path.exists(path):
            raise SystemExit(f'원문 파일이 없어요: {path}')
        texts[pid] = open(path, encoding='utf-8').read()
    missing = {g['사용자'] for g in rows} - set(users)
    if missing:
        raise SystemExit(f'사용자 파일에 없는 사용자: {sorted(missing)}')
    print(f'{len(rows)}쌍, 공고 {len(texts)}건, 모델 {a.model}')

    out, raw = [], []
    tokens = Counter()
    start = time.time()
    for i, g in enumerate(rows, 1):
        msg = user_message(g['공고ID'], texts[g['공고ID']], users[g['사용자']])
        data, usage, err = judge(client, a.model, system, msg)
        if usage:
            tokens['입력'] += usage.prompt_tokens
            tokens['캐시'] += getattr(usage.prompt_tokens_details, 'cached_tokens', 0) or 0
            tokens['출력'] += usage.completion_tokens
        out.append(to_row(g, data, err))
        raw.append({'사용자': g['사용자'], '공고ID': g['공고ID'], '응답': data, '오류': err})
        mark = emoji(out[-1].get('예측')) or '실패 ' + err
        print(f'[{i}/{len(rows)}] {g["사용자"]} {g["공고ID"]} → {mark}  (정답 {emoji(g["정답"])})')
    elapsed = time.time() - start

    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)
    base = os.path.splitext(a.out)[0]
    with open(base + '.raw.json', 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)

    # 비용
    p_in, p_cache, p_out = PRICES.get(a.model, (0, 0, 0))
    cost = ((tokens['입력'] - tokens['캐시']) * p_in + tokens['캐시'] * p_cache
            + tokens['출력'] * p_out) / 1e6
    print(f'\n토큰: 입력 {tokens["입력"]:,} (캐시 {tokens["캐시"]:,}), 출력 {tokens["출력"]:,}')
    print(f'비용 ${cost:.3f}, 시간 {elapsed:.0f}초 (1쌍 {elapsed / len(rows):.1f}초)')

    # 채점: 전체, 그리고 개발/평가가 섞여 있으면 따로
    gold = {(g['사용자'], g['공고ID']): emoji(g['정답']) for g in rows}
    result = {'모델': a.model, '프롬프트': os.path.basename(a.prompt), '비용(USD)': round(cost, 4), '토큰': dict(tokens)}
    groups = {'전체': out, '개발': [r for r in out if r['공고ID'] in DEV_IDS], '평가': [r for r in out if r['공고ID'] not in DEV_IDS]}
    for name, sub in groups.items():
        if not sub or (name != '전체' and len(sub) == len(out)):
            continue
        m = metrics([(gold[(r['사용자'], r['공고ID'])], emoji(r.get('예측'))) for r in sub])
        result[name] = m
        print(f'\n[{name} {m["쌍 수"]}쌍] Accuracy {m["Accuracy"]}, False green {m["False green"]}'
              f' (🟢 예측 {m["🟢 예측 수"]}건), Macro-F1 {m["Macro-F1"]}')
        print('  혼동행렬(정답→예측):', m['혼동행렬(정답→예측)'])
    with open(base + '.metrics.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
