#!/usr/bin/env python3
"""B0: API 칸 필터 (기준선)

공고의 API 칸(해시태그의 지역, 지원대상)만으로 사용자 x 공고를 🟢/🔴로 가른다.
원문은 읽지 않는다. 그래서 🟡·⚪는 낼 수 없다.

규칙
  1) 지역: 해시태그에 시도 이름이 있고 '전국(시도 15개 이상)'이 아니면,
     사용자의 거주지·창업예정지·사업장소재지 시도 중 하나가 해시태그에 있어야 통과.
     서울 공고의 해시태그에 서울 구 이름이 있으면, 사용자의 거주지·창업예정지·사업장소재지
     구 중 하나가 그 구여야 통과 (해시태그로는 거주지 기준인지 사업장 기준인지 알 수 없어
     셋 중 하나만 맞아도 통과). --sido-only 를 주면 예전처럼 시도까지만 본다.
  2) 지원대상: '소상공인'이면 사업자 보유자만 통과, 그 밖의 값('창업벤처' 등)은 모두 통과.
     사업자 보유 = users.csv의 창업단계가 '초기창업' (예전 값 '기창업', 예전 사용자 파일의 사업자이력='현재보유'도 인정)
  3) 둘 다 통과하면 🟢, 아니면 🔴.
  --ignore-region 을 주면 1)을 건너뛴다(지역 제외 정답과 비교할 때 사용).

"""
import argparse, csv, json
from collections import Counter

SIDO_TAGS = {
    '서울특별시': {'서울', '서울특별시'}, '부산광역시': {'부산', '부산광역시'},
    '대구광역시': {'대구', '대구광역시'}, '인천광역시': {'인천', '인천광역시'},
    '전남광주통합특별시': {'전남광주', '전남광주통합특별시', '전남', '전라남도', '광주', '광주광역시'},
    '대전광역시': {'대전', '대전광역시'}, '울산광역시': {'울산', '울산광역시'},
    '세종특별자치시': {'세종', '세종특별자치시'}, '경기도': {'경기', '경기도'},
    '강원특별자치도': {'강원', '강원특별자치도', '강원도'}, '충청북도': {'충북', '충청북도'},
    '충청남도': {'충남', '충청남도'}, '전북특별자치도': {'전북', '전북특별자치도', '전라북도'},
    '경상북도': {'경북', '경상북도'}, '경상남도': {'경남', '경상남도'},
    '제주특별자치도': {'제주', '제주특별자치도'},
}
ALL_TAGS = set().union(*SIDO_TAGS.values())
SEOUL_GU = {'종로구', '중구', '용산구', '성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구',
            '도봉구', '노원구', '은평구', '서대문구', '마포구', '양천구', '강서구', '구로구', '금천구',
            '영등포구', '동작구', '관악구', '서초구', '강남구', '송파구', '강동구'}
LABELS = ['🟢', '🟡', '⚪', '🔴']


def rows(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def user_places(u, key):
    """거주지·창업예정지·사업장소재지(JSON)에서 key('시도' 또는 '시군구') 값을 모은다."""
    out = set()
    for k in ('거주지', '창업예정지', '사업장소재지'):
        if u.get(k):
            try:
                v = json.loads(u[k]).get(key)
                if v:
                    out.add(v)
            except Exception:
                pass
    return out


def has_business(u):
    """사업자 보유 여부. 새 users.csv는 창업단계, 예전 파일은 사업자이력 칸을 쓴다."""
    return u.get('사업자이력') == '현재보유' or u.get('창업단계') in ('초기창업', '기창업')


def region_ok(tags, u, sido_only=False):
    post = tags & ALL_TAGS
    n_sido = sum(1 for t in SIDO_TAGS.values() if t & post)
    if not post or n_sido >= 15:      # 지역 표기 없음 또는 전국
        return True
    if not any(SIDO_TAGS.get(s, set()) & post for s in user_places(u, '시도')):
        return False
    gus = tags & SEOUL_GU
    if sido_only or not gus or not (post & SIDO_TAGS['서울특별시']):
        return True                    # 구 표기 없음 → 시도만 맞으면 통과
    return bool(gus & user_places(u, '시군구'))


def emoji(label):
    """'🟢 신청 가능', '⚪️ 확인 필요' 등에서 앞 이모지만 남긴다."""
    label = (label or '').strip().replace('️', '')
    return label[:1]


def evaluate(gold, out):
    pairs = [(emoji(g['정답']), emoji(o['예측'])) for g, o in zip(gold, out)]
    n = len(pairs)
    green = [g for g, p in pairs if p == '🟢']
    f1 = {}
    for c in LABELS:
        tp = sum(g == c and p == c for g, p in pairs)
        fp = sum(g != c and p == c for g, p in pairs)
        fn = sum(g == c and p != c for g, p in pairs)
        pr = tp / (tp + fp) if tp + fp else 0
        rc = tp / (tp + fn) if tp + fn else 0
        f1[c] = 2 * pr * rc / (pr + rc) if pr + rc else 0
    print(f'쌍 수: {n}')
    print(f'Accuracy: {sum(g == p for g, p in pairs) / n:.3f}')
    wrong = sum(g != '🟢' for g in green)
    print(f'False green: {wrong / len(green) if green else 0:.3f}  (🟢로 안내한 {len(green)}건 중 {wrong}건 오답)')
    print(f'Macro-F1 (4클래스): {sum(f1.values()) / 4:.3f}  ' + ', '.join(f'{c} {v:.3f}' for c, v in f1.items()))
    print('정답 분포:', dict(Counter(g for g, _ in pairs)))
    print('예측 분포:', dict(Counter(p for _, p in pairs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--users', required=True); ap.add_argument('--gold', required=True)
    ap.add_argument('--api', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--ignore-region', action='store_true')
    ap.add_argument('--sido-only', action='store_true', help='지역을 시도까지만 비교(예전 B0)')
    ap.add_argument('--eval', action='store_true', help='정답과 비교해 지표 출력')
    a = ap.parse_args()
    users = {u['사용자ID']: u for u in rows(a.users)}
    api = {r['공고ID']: r for r in rows(a.api)}
    gold = rows(a.gold)
    missing = sorted({g['공고ID'] for g in gold} - set(api))
    if missing:
        raise SystemExit(f'api 파일에 없는 공고ID {len(missing)}건: {missing}')
    out = []
    for g in gold:
        u, p = users[g['사용자']], api[g['공고ID']]
        tags = {t.strip() for t in p['해시태그'].split(',')}
        ok_reg = True if a.ignore_region else region_ok(tags, u, a.sido_only)
        ok_tgt = has_business(u) if '소상공인' in p['지원대상'] else True
        why = []
        if not ok_reg: why.append('지역 칸 불일치')
        if not ok_tgt: why.append('지원대상 칸(소상공인) 불일치')
        out.append({'사용자': g['사용자'], '공고ID': g['공고ID'],
                    '예측': '🟢 신청 가능' if ok_reg and ok_tgt else '🔴 신청 불가',
                    '근거 문장': '', '사유': ', '.join(why)})
    with open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['사용자', '공고ID', '예측', '근거 문장', '사유'])
        w.writeheader(); w.writerows(out)
    print(f'B0 예측 {len(out)}건 저장: {a.out}')
    if a.eval:
        evaluate(gold, out)


if __name__ == '__main__':
    main()
