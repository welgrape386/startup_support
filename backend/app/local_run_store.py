"""Explicitly opt-in local experiment persistence. Do not persist prompts by default."""
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.extended_models import UserRequest, MatchRun, MatchResult

def maybe_save_demo_run(session: Session, payload: dict) -> None:
    if os.getenv('SAVE_DEMO_RUNS', '0') != '1':
        return
    profile=payload['profile']
    request=UserRequest(
        input_text=profile['freeText'],profile_json=profile,
        age=profile['age']['value'],startup_months=None,gender=None,is_registered=None,sido=profile['sido']['value'],
        sigungu=profile['sigungu']['value'],biz_stage=profile['bizStage']['value'],
        startup_stage=profile['bizStage']['value'], business_type=profile['industryCategory']['value'],
        funding_gap=profile['fundingGapManwon']['value'], needs_json=profile['needs'])
    session.add(request);session.flush()
    run=MatchRun(request_id=request.request_id,execution_status='success',
                 data_source='local_demo',search_version='keyword_v1',parser_version='rule_v1',
                 data_snapshot='bizinfo_selected_342_20261024',
                 summary_json=payload['summary'],coverage_json=payload['coverage'],
                 completed_at=datetime.now(timezone.utc).replace(tzinfo=None))
    session.add(run);session.flush()
    for rank,r in enumerate(payload['results'],start=1):
        session.add(MatchResult(run_id=run.run_id,
            announcement_id=r['program']['id'],
            verdict=r['verdict'],verdict_source='demo_unverified',
            score=r['score'],search_score=r.get('searchScore'),judgment_score=r.get('judgmentScore'),rank_number=rank,headline=r['headline'],
            reasons_json=r['reasons'],cautions_json=r['cautions'],exceptions_json=r['exceptions']))
    session.commit()
