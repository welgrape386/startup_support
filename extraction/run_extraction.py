"""조건 추출 실행: prompts/extract_v1.md 의 [프롬프트 본문]만 지시문으로 보내고, 공고 원문을 입력으로 보내 JSON을 받는다

사용법:
  python run_extraction.py --only PBLN_000000000121175 --out results/extract_v1_dev_luna     # 한 건만 시험
  python run_extraction.py --out results/extract_v1_dev_luna                                  # 개발 15건
  python run_extraction.py --model gpt-6.1-sol --out results/extract_v1_dev_sol               # 모델 바꾸기
  python run_extraction.py --ids prompts/target_ids_gold30_v3_eval.txt --out results/extract_v1_eval_luna
  python run_extraction.py --prompt prompts/extract_v2.md --model gpt-6.1-terra --out results/extract_v2_dev_terra   # 프롬프트 바꾸기
  (이미 있는 결과는 건너뜀, 다시 하려면 --force)

- 모델: gpt-* 는 OpenAI, claude-* 는 Anthropic. 기본 gpt-6-luna
- API 키: 환경변수 또는 .env 의 OPENAI_API_KEY / ANTHROPIC_API_KEY (값은 출력하지 않음)
- 프롬프트 파일 머리말(변경 이력·확정 전 항목)과 [실행 지시]는 보내지 않는다 (정답셋에서 나온 정보가 있음)
- 정답셋(gold/)은 읽지 않는다
- 끝나면 conditions_*.json 으로 모으고 verify_extraction.py 를 돌린다
"""
import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPT = ROOT / "prompts/extract_v1.md"
TEXTS = ROOT / "output/texts"
MAX_TOKENS = 64000
TIMEOUT = 1200  # 초. 긴 공고는 생각(reasoning)이 길어질 수 있음
# $/1M 토큰. OpenAI 는 2026-11-07 developers.openai.com/api/docs/pricing 기준(입력 27.2만 토큰 이하), Anthropic 은 2026-10 기준
PRICES = {
    "gpt-6-luna": {"input": 0.10, "cache_read": 0.01, "cache_write": 0.10, "output": 0.50},
    "gpt-6.1-terra": {"input": 1.00, "cache_read": 0.05, "cache_write": 1.00, "output": 5.00},
    "gpt-6.1-sol": {"input": 2.00, "cache_read": 0.10, "cache_write": 2.00, "output": 10.00},
    "claude-haiku-5-5": {"input": 0.10, "cache_read": 0.01, "cache_write": 0.125, "output": 0.50},
    "claude-sonnet-5-5": {"input": 2.00, "cache_read": 0.20, "cache_write": 2.50, "output": 10.00},
    "claude-opus-5-5": {"input": 4.00, "cache_read": 0.20, "cache_write": 5.00, "output": 20.00},
}
CLAUDE_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}  # 거절 시 서버가 다른 모델로 다시 돌림


def load_env(name):
    """.env 의 name 값을 환경변수로 (이미 있으면 그대로)"""
    env = ROOT / ".env"
    if os.environ.get(name) or not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{name}="):
            os.environ[name] = line.split("=", 1)[1].strip().strip('"').strip("'")


def prompt_body():
    """[프롬프트 본문] 절만 잘라낸다 ([실행 지시] 전까지)"""
    text = PROMPT.read_text(encoding="utf-8")
    start = text.index("## [프롬프트 본문]")
    end = text.index("## [실행 지시]")
    body = text[start:end].split("\n", 1)[1].strip()
    return body.rstrip("-").strip()


def is_info():
    """안내정보 프롬프트(prompts/info_v*.md)인가 (11/16)"""
    return PROMPT.stem.startswith("info")


def info_inputs(pid):
    """안내정보 추출에 같이 주는 것: API 접수기간, 자격 추출의 트랙 이름 (서비스 데이터)"""
    period = ""
    for f in sorted((ROOT / "data").glob("bizinfo_all_*.csv")):
        with open(f, encoding="utf-8-sig") as fh:
            period = next((r["reqstBeginEndDe"] for r in csv.DictReader(fh) if r["pblancId"] == pid), period)
    cond = ROOT / "results/service_v4_업종확장" / f"{pid}.json"
    tracks = [t["이름"] for t in json.loads(cond.read_text(encoding="utf-8")).get("트랙") or []] if cond.exists() else []
    return period, tracks


def user_message(pid):
    raw = (TEXTS / f"{pid}.txt").read_text(encoding="utf-8")
    if is_info():
        period, tracks = info_inputs(pid)
        return (f"공고ID: {pid}\nAPI 접수기간: {period or '(없음)'}\n자격 추출 트랙 이름: {json.dumps(tracks, ensure_ascii=False)}\n\n"
                f"<원문>\n{raw}\n</원문>\n\n위 원문에서 규칙대로 안내정보를 뽑아 JSON 하나만 출력해.")
    return f"공고ID: {pid}\n\n<원문>\n{raw}\n</원문>\n\n위 원문에서 규칙대로 자격 조건을 뽑아 JSON 하나만 출력해."


def parse_json(text):
    """모델 출력에서 JSON 객체 하나를 꺼낸다 (코드블록 표시가 붙어 와도 처리)"""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(t[t.find("{"):t.rfind("}") + 1])


def cost(u, price):
    return sum(u[k] * price[k] for k in ("input", "cache_read", "cache_write", "output")) / 1e6


class OpenAIRunner:
    def __init__(self, model, effort, instructions):
        import openai
        load_env("OPENAI_API_KEY")
        self.openai, self.model, self.effort, self.instructions = openai, model, effort, instructions
        self.client = openai.OpenAI(timeout=TIMEOUT)
        self.errors = (openai.RateLimitError, openai.APIStatusError, openai.APIConnectionError)

    def extract(self, pid):
        """반환: (출력 텍스트, 끝난 이유, 실제 모델, 토큰 사용량)"""
        r = self.client.responses.create(
            model=self.model, instructions=self.instructions, input=user_message(pid),
            reasoning={"effort": self.effort}, max_output_tokens=MAX_TOKENS,
            text={"format": {"type": "json_object"}},
            prompt_cache_key=PROMPT.stem, store=False,
        )
        u = r.usage
        cached = (u.input_tokens_details.cached_tokens or 0) if u.input_tokens_details else 0
        usage = {"input": u.input_tokens - cached, "cache_read": cached, "cache_write": 0, "output": u.output_tokens,
                 "reasoning": (u.output_tokens_details.reasoning_tokens or 0) if u.output_tokens_details else 0}
        reason = r.status if r.status != "incomplete" else f"incomplete:{r.incomplete_details.reason}"
        return r.output_text, reason, r.model, usage


class ClaudeRunner:
    def __init__(self, model, effort, instructions):
        import anthropic
        load_env("ANTHROPIC_API_KEY")
        self.model = model
        self.client = anthropic.Anthropic(timeout=TIMEOUT)
        self.errors = (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError)
        self.system = [{"type": "text", "text": instructions, "cache_control": {"type": "ephemeral"}}]
        # output_config·fallbacks 는 설치된 SDK(0.92)가 모르는 칸이라 extra_body 로 보낸다
        self.extra_body, self.extra_headers = {"output_config": {"effort": effort}}, {}
        if model in CLAUDE_FALLBACK_MODELS:
            self.extra_body["fallbacks"] = "default"
            self.extra_headers["anthropic-beta"] = "server-side-fallback-2026-07-01"

    def extract(self, pid):
        with self.client.messages.stream(
            model=self.model, max_tokens=MAX_TOKENS, system=self.system,
            messages=[{"role": "user", "content": user_message(pid)}],
            extra_body=self.extra_body, extra_headers=self.extra_headers,
        ) as stream:
            msg = stream.get_final_message()
        u = msg.usage
        usage = {"input": u.input_tokens or 0, "cache_read": u.cache_read_input_tokens or 0,
                 "cache_write": u.cache_creation_input_tokens or 0, "output": u.output_tokens or 0, "reasoning": ""}
        reason = "completed" if msg.stop_reason == "end_turn" else msg.stop_reason
        return "".join(b.text for b in msg.content if b.type == "text"), reason, msg.model, usage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="prompts/target_ids_gold30_v3_dev.txt")
    ap.add_argument("--out", required=True, help="결과 폴더 (모델마다 따로, 예: results/extract_v1_dev_luna)")
    ap.add_argument("--only", help="이 공고ID 하나만")
    ap.add_argument("--force", action="store_true", help="이미 있는 결과도 다시 추출")
    ap.add_argument("--model", default="gpt-6-luna", choices=sorted(PRICES))
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--prompt", default="prompts/extract_v1.md", help="프롬프트 파일 (예: prompts/extract_v2.md)")
    args = ap.parse_args()
    global PROMPT
    PROMPT = ROOT / args.prompt
    if "## [실행 지시]" not in PROMPT.read_text(encoding="utf-8"):
        sys.exit(f"{PROMPT}: '## [실행 지시]' 제목이 없어 프롬프트 본문 끝을 찾을 수 없음")

    instructions = prompt_body()
    Runner = OpenAIRunner if args.model.startswith("gpt") else ClaudeRunner
    runner = Runner(args.model, args.effort, instructions)
    price = PRICES[args.model]
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    ids = [l.strip() for l in (ROOT / args.ids).read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.only:
        ids = [args.only]

    # 실행 정보 (어떤 모델·설정·프롬프트로 돌렸는지)
    (out / "run_info.json").write_text(json.dumps({
        "model": args.model, "effort": args.effort, "max_output_tokens": MAX_TOKENS,
        "prompt_file": str(PROMPT.relative_to(ROOT)),
        "prompt_body_sha256_12": hashlib.sha256(instructions.encode("utf-8")).hexdigest()[:12],
        "ids_file": args.ids, "started": datetime.now().isoformat(timespec="seconds")},
        ensure_ascii=False, indent=2), encoding="utf-8")

    log_path = out / "run_log.csv"
    new_log = not log_path.exists()
    spent = 0.0
    with open(log_path, "a", encoding="utf-8-sig", newline="") as lf:
        log = csv.writer(lf)
        if new_log:
            log.writerow(["공고ID", "served_model", "끝난이유", "input", "cache_read", "cache_write", "output",
                          "그중_reasoning", "cost_usd", "json_ok", "time"])
        for k, pid in enumerate(ids, 1):
            dest = out / f"{pid}.json"
            if dest.exists() and not args.force:
                print(f"[{k}/{len(ids)}] {pid} 이미 있음, 건너뜀")
                continue
            print(f"[{k}/{len(ids)}] {pid} 추출 중...", flush=True)
            try:
                text, reason, served, u = runner.extract(pid)
            except runner.errors as e:
                print(f"  API 오류: {type(e).__name__}: {getattr(e, 'message', e)}")
                log.writerow([pid, "", f"error {type(e).__name__}", "", "", "", "", "", "", False,
                              datetime.now().isoformat(timespec="seconds")])
                if type(e).__name__ in ("RateLimitError", "APIConnectionError", "AuthenticationError"):
                    break
                continue

            c = cost(u, price)
            spent += c
            ok = False
            if reason != "completed":
                print(f"  정상 종료 아님: {reason}")
            else:
                try:
                    data = parse_json(text)
                    data["공고ID"] = pid
                    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    ok = True
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"  JSON 파싱 실패: {e}")
            if not ok:
                (out / f"{pid}.raw.txt").write_text(text or "", encoding="utf-8")
            log.writerow([pid, served, reason, u["input"], u["cache_read"], u["cache_write"], u["output"],
                          u["reasoning"], f"{c:.5f}", ok, datetime.now().isoformat(timespec="seconds")])
            lf.flush()
            print(f"  {reason}, 입력 {u['input'] + u['cache_read']:,} / 출력 {u['output']:,} 토큰"
                  f" (생각 {u['reasoning'] or '-'}), ${c:.4f} ≈ {c * 1400:,.0f}원 (누적 ${spent:.3f})")

    files = sorted(out.glob("PBLN_*.json"))
    merged = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    name = f"info_{out.name.replace('info_', '')}.json" if is_info() else f"conditions_{out.name.replace('extract_', '')}.json"
    (out / name).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(files)}건 → {out / name}")
    subprocess.run([sys.executable, str(ROOT / ("verify_info.py" if is_info() else "verify_extraction.py")), str(out)],
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})


if __name__ == "__main__":
    main()
