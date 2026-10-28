"""One sentence -> JSON CLI. From repository root: python run_extract.py --text ..."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from user_extraction import extract_user_info
from user_extraction.demo_rules import demo_extract

def main(argv=None):
    ap=argparse.ArgumentParser(description='사용자 자연어 → AI 추출 JSON')
    ap.add_argument('--text',help='분석할 사용자 자연어. 생략하면 입력 요청')
    ap.add_argument('--mode',choices=['llm','demo'],default='llm',help='llm=실제 LLM, demo=오프라인 규칙 검증')
    ap.add_argument('--model',help='OpenAI 모델 (생략 시 OPENAI_MODEL 환경변수)')
    ap.add_argument('--user-id',help='기존 사용자 ID; 임의로 발급하지 않음')
    ap.add_argument('--out',help='결과 JSON 저장 파일 (옵션)')
    args=ap.parse_args(argv)
    load_dotenv(Path(__file__).with_name('.env'))
    raw=args.text if args.text is not None else input('사용자 문장을 입력하세요: ')
    try:
        result=(demo_extract(raw,user_id=args.user_id) if args.mode=='demo'
                else extract_user_info(raw,user_id=args.user_id,model=args.model))
    except Exception as exc:
        print(f'추출 실패: {exc}',file=sys.stderr)
        return 1
    output=json.dumps(result,ensure_ascii=False,indent=2)
    print(output)
    if args.out:
        path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(output+'\n',encoding='utf-8')
        print(f'결과 저장: {path}',file=sys.stderr)
    if args.mode=='demo':print('[주의] demo는 LLM이 아닌 제한적인 규칙 기반 미리보기입니다.',file=sys.stderr)
    return 0

if __name__=='__main__':raise SystemExit(main())
