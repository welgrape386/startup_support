"""Explicitly opt-in local experiment persistence. Do not persist prompts by default."""
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.extended_models import UserRequest, MatchRun, MatchResult


def _build_user_request(input_text: str, profile: dict, extract_raw: dict | None = None) -> UserRequest:
    """UserRequest 객체 생성.

    extract_raw: 나애님 user_extract v2 flat dict (있을 때 우선 사용).
    profile: 기존 local_demo 형태 (없으면 None).
    """
    if extract_raw:
        # 나애님 출력 형식 (DB 컬럼명 그대로)
        stage = extract_raw.get('stage')
        # 사업장 위치: 예비창업 → plan, 초기창업 → biz
        biz_prefix = 'plan' if stage != '초기창업' else 'biz'
        sido = extract_raw.get(f'{biz_prefix}_sido') or extract_raw.get('res_sido')
        sigungu = extract_raw.get(f'{biz_prefix}_sigungu') or extract_raw.get('res_sigungu')
        profile_json = {**extract_raw, '_source': 'user_extract_v2'}
        return UserRequest(
            input_text=input_text,
            profile_json=profile_json,
            age=extract_raw.get('age'),
            startup_months=extract_raw.get('biz_months'),
            gender=extract_raw.get('gender'),
            is_registered=None,  # biz_type으로 추론 가능하나 별도 판단 필요
            sido=sido,
            sigungu=sigungu,
            biz_stage=stage,
            startup_stage=stage,
            business_type=(
                '|'.join(extract_raw['industry_cat'])
                if extract_raw.get('industry_cat') else
                extract_raw.get('industry_raw')
            ),
            funding_gap=None,
            needs_json=extract_raw.get('need'),
        )
    else:
        # 기존 local_demo profile 형태 (fallback)
        return UserRequest(
            input_text=input_text,
            profile_json=profile,
            age=profile['age']['value'],
            startup_months=None,
            gender=None,
            is_registered=None,
            sido=profile['sido']['value'],
            sigungu=profile['sigungu']['value'],
            biz_stage=profile['bizStage']['value'],
            startup_stage=profile['bizStage']['value'],
            business_type=profile['industryCategory']['value'],
            funding_gap=profile['fundingGapManwon']['value'],
            needs_json=profile['needs'],
        )


def maybe_save_demo_run(
    session: Session,
    payload: dict,
    extract_raw: dict | None = None,
) -> int | None:
    """SAVE_DEMO_RUNS=1 일 때만 저장. request_id 반환 (저장 안 하면 None)."""
    if os.getenv('SAVE_DEMO_RUNS', '0') != '1':
        return None

    profile = payload['profile']
    input_text = (
        extract_raw.get('input_text', '')
        if extract_raw else
        profile.get('freeText', '')
    )

    request = _build_user_request(input_text, profile, extract_raw)
    session.add(request)
    session.flush()

    run = MatchRun(
        request_id=request.request_id,
        execution_status='success',
        data_source='local_demo',
        search_version='keyword_v1',
        parser_version='rule_v1' if not extract_raw else 'naeye_v2',
        data_snapshot='bizinfo_selected_342_20261024',
        summary_json=payload['summary'],
        coverage_json=payload['coverage'],
        completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(run)
    session.flush()

    for rank, r in enumerate(payload['results'], start=1):
        session.add(MatchResult(
            run_id=run.run_id,
            announcement_id=r['program']['id'],
            verdict=r['verdict'],
            verdict_source='demo_unverified',
            score=r['score'],
            search_score=r.get('searchScore'),
            judgment_score=r.get('judgmentScore'),
            rank_number=rank,
            headline=r['headline'],
            reasons_json=r['reasons'],
            cautions_json=r['cautions'],
            exceptions_json=r['exceptions'],
        ))

    session.commit()
    return request.request_id


def save_user_request(
    session: Session,
    extract_raw: dict,
    mode: str = 'rules',
) -> int | None:
    """user-extract 단독 호출(llm 모드) 시 user_requests에 저장.

    SAVE_DEMO_RUNS=1 일 때만 저장. request_id 반환.
    """
    if os.getenv('SAVE_DEMO_RUNS', '0') != '1':
        return None

    request = _build_user_request(
        input_text=extract_raw.get('input_text', ''),
        profile={},
        extract_raw=extract_raw,
    )
    session.add(request)
    session.commit()
    return request.request_id
