"""Evaluate all 28 original questions. Honest, strict string-label comparison."""
from __future__ import annotations
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv
from user_extraction import extract_user_info
from user_extraction.demo_rules import demo_extract

ROOT=Path(__file__).parent
DEFAULT_CSV=ROOT/'fixtures'/'search_questions.csv'
# 'size' and 'difficulty' are owned by the retrieval evaluation team.
# User extraction accuracy only scores these nine gold fields.
NEED_KEYS=['need','age','region','stage','biz_months','biz_type','gender','industry','fund']

def get_prediction(result:dict)->dict:
    p=result['사용자프로필'];s=result['검색정보'];e=result['추가추출값']
    form=p['기업형태']
    bt={'개인사업자':'개인','법인':'법인'}.get(form,'')
    if not bt and e['현재사업자등록상태']=='미등록':bt='미등록'
    amount=e['자금_언급_원']
    return {
      'need': '|'.join(s['필요지원']),
      'age': str(e['나이_언급']) if e['나이_언급'] is not None else '',
      'region':s['검색지역'] or '',
      'stage':e['창업단계_언급'] or '',
      'biz_months':str(e['업력_개월']) if e['업력_개월'] is not None else '',
      'biz_type':bt,
      'size':e['기업규모_표현'] or '',
      'gender':p['성별'] or '',
      'industry':s['업종원문표현'] or '',
      'fund':f'{amount//10000000}천만원' if amount is not None and amount%10000000==0 else (str(amount) if amount is not None else ''),
    }

def compare_field(key:str,gold:str,pred:str)->bool:
    if key=='need':return set(gold.split('|'))==set(pred.split('|'))
    return gold.strip()==pred.strip()

def evaluate(mode='llm',csv_path:Path=DEFAULT_CSV,out_dir:Path=ROOT/'output',model=None):
    with csv_path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if not rows:raise ValueError('테스트 CSV가 비어 있습니다.')
    for key in ['qid','question',*NEED_KEYS]:
        if key not in rows[0]:raise ValueError(f'CSV에 {key} 열이 없습니다.')
    out_dir.mkdir(parents=True,exist_ok=True)
    results=[];count=defaultdict(int);correct=defaultdict(int);errors=[]
    for row in rows:
        qid=row['qid'];question=row['question']
        try:
            extracted=(demo_extract(question,user_id=qid) if mode=='demo' else extract_user_info(question,user_id=qid,model=model))
            pred=get_prediction(extracted)
        except Exception as exc:
            errors.append({'qid':qid,'error':str(exc)})
            pred={k:'' for k in NEED_KEYS};extracted=None
        result_row={'qid':qid,'difficulty':row.get('difficulty',''),'question':question}
        for key in NEED_KEYS:
            gold=row.get(key,'').strip();prediction=pred.get(key,'')
            passed=compare_field(key,gold,prediction) if extracted else False
            result_row.update({f'{key}_gold':gold,f'{key}_pred':prediction,f'{key}_ok':int(passed)})
            count[key]+=1;correct[key]+=int(passed)
        results.append(result_row)
        if extracted is not None:
            # User text and generated profile may be personal: keep local, never commit output directory.
            out_path=out_dir/f'{qid}.json'
            out_path.write_text(json.dumps(extracted,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'{qid} 평가 완료',file=sys.stderr)
    cols=list(results[0].keys())
    with (out_dir/'test_results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader();writer.writerows(results)
    report={
      'mode':mode,'test_total':len(rows),'successful_extractions':len(rows)-len(errors),
      'note':('OFFLINE DEMO RULES ONLY. These numbers are NOT LLM accuracy.' if mode=='demo'
              else 'Actual API-backed LLM run. Strict exact-match label accuracy; check semantic equivalence manually.'),
      'field_accuracy':{k:{'correct':correct[k],'total':count[k],
                             'accuracy':round(correct[k]/count[k],4)} for k in NEED_KEYS},
      'failed_calls':errors,
      'unscored_fields':['필요지원키워드','상황키워드','KSIC 코드'],
      'evaluation_limitations':['원본 정답 CSV는 일부 자유표현을 축약한 정답이며 뜻이 같아도 exact-match가 틀렸다고 판정할 수 있음',
                                '키워드/상황 키워드 정답은 첨부 CSV에 존재하지 않음',
                                '공란도 정확히 미추출했는지 점검 대상에 포함됨']
    }
    (out_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report

def main():
    ap=argparse.ArgumentParser(description='search_questions.csv 자동 평가')
    ap.add_argument('--mode',choices=['llm','demo'],default='llm')
    ap.add_argument('--model')
    ap.add_argument('--csv',type=Path,default=DEFAULT_CSV)
    ap.add_argument('--out-dir',type=Path,default=ROOT/'output')
    args=ap.parse_args()
    load_dotenv(ROOT/'.env')
    if args.mode=='llm':
        import os
        if not os.getenv('OPENAI_API_KEY'):
            print('OPENAI_API_KEY가 없습니다. 28건 LLM 평가를 실행하지 않았습니다. --mode demo는 구조 검증만 합니다.',file=sys.stderr)
            return 2
    report=evaluate(mode=args.mode,csv_path=args.csv,out_dir=args.out_dir,model=args.model)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if not report['failed_calls'] else 1

if __name__=='__main__':raise SystemExit(main())
