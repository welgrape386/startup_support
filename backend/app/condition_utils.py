"""Conservative projection: never flatten multi-track/OR logic into a single filter."""
from typing import Any

REQUIRED_FIELDS = {'공고ID', '스키마버전', '신청자_유형', '나이', '성별', '지역', '업력', '사업자등록', '창업이력', '업종', '기업규모', '보유요건', '특수자격', '제외대상', '대안조건', '기타조건', '트랙'}
VALID_STATES = {'있음', '없음', '불명확', '대안조건'}


def validate_condition(data: Any, announcement_id: str) -> None:
    if not isinstance(data, dict):
        raise ValueError('조건 추출 결과는 JSON object이어야 합니다')
    if data.get('공고ID') != announcement_id:
        raise ValueError(f'공고ID 불일치: {announcement_id} / {data.get("공고ID")}')
    missing = REQUIRED_FIELDS - set(data)
    if missing:
        raise ValueError(f'스키마의 필수 최상위 필드 누락: {sorted(missing)}')
    if not isinstance(data.get('스키마버전'), str):
        raise ValueError('스키마버전 문자열이 필요합니다')
    for key in ['신청자_유형', '나이', '성별', '지역', '업력', '사업자등록', '창업이력', '업종', '기업규모']:
        obj = data[key]
        if not isinstance(obj, dict) or obj.get('상태') not in VALID_STATES:
            raise ValueError(f'{key}.상태 누락 또는 잘못된 상태')
    for key in ['보유요건', '특수자격', '제외대상', '대안조건', '기타조건', '트랙']:
        if not isinstance(data[key], list):
            raise ValueError(f'{key}는 배열이어야 합니다')


def _plain(data, key):
    item = data.get(key)
    return item if isinstance(item, dict) and item.get('상태') == '있음' else {}


def projection(data: dict) -> dict:
    result = dict(sido=None, business_registration=None, max_startup_months=None, max_age=None)
    # An OR or track-specific rule cannot be faithfully represented by a single-value filter.
    if data.get('대안조건') or data.get('트랙'):
        return result
    region = _plain(data, '지역')
    scope = region.get('범위')
    if isinstance(scope, list) and len(scope) == 1 and isinstance(scope[0], dict):
        loc = scope[0]
        if isinstance(loc.get('시도'), str) and loc['시도'].strip() and not loc.get('권역') and not loc.get('시군구'):
            result['sido'] = loc['시도']
    business = _plain(data, '사업자등록').get('값')
    if business in ('필수', '불가'):
        result['business_registration'] = business
    startup = _plain(data, '업력').get('max_개월')
    if type(startup) is int and startup >= 0:
        result['max_startup_months'] = startup
    age = _plain(data, '나이')
    max_age = age.get('max')
    if type(max_age) is int and max_age >= 0 and age.get('대상') in ('신청자_본인', '대표자'):
        result['max_age'] = max_age
    return result
