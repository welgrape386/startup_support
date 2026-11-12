/* 입력 검증과 LLM 설명 검증 (명세 4-4, 결정 g·h). 원문·구조화 필드와 대조해 실패한 문장은 버린다 */

import { MAX_TEXT_LENGTH } from './config'
import type { MatchResult, MatchVerdict, ProgramChunk, RuleResult, SupportProgram } from './types'

/** 클라이언트 버튼 비활성화와 서버 400 INVALID_INPUT 이 같이 쓴다. 문제 없으면 null */
export function inputError(text: string): string | null {
  const len = text.trim().length
  return len < 1 || len > MAX_TEXT_LENGTH ? `1~${MAX_TEXT_LENGTH}자로 입력해주세요.` : null
}

/** NFC + 공백·줄바꿈 하나로 */
export const normalizeText = (s: string) => s.normalize('NFC').replace(/\s+/g, ' ').trim()

const UNIT: Record<string, number> = { 억: 10000, 천만: 1000, 만: 1 }

/** 문장 속 숫자. 금액(억·천만·만 단위)은 만원으로 환산(1억 → 10000)하고 money 표시 */
export function numbersIn(s: string): { n: number; money: boolean }[] {
  return [...s.matchAll(/(\d[\d,]*(?:\.\d+)?)\s*(억|천\s*만|만)?/g)].map(([, n, u]) => ({
    n: parseFloat(n.replace(/,/g, '')) * (u ? UNIT[u.replace(/\s/g, '')] : 1),
    money: !!u,
  }))
}

const values = (s?: string) => (s ? numbersIn(s).map((x) => x.n) : [])

/** 설명에 써도 되는 숫자: 1인당 한도, 나이 범위, 마감일, 금리. totalBudgetText(전체 예산)는 넣지 않는다 */
function structuredNumbers(p: SupportProgram): number[] {
  return [
    p.amountMaxManwon,
    ...p.eligibility.flatMap((g) => g.rules).flatMap((r) => (r.kind === 'age' ? [r.min, r.max] : [])),
    ...values(p.applyEnd),
    ...values(p.interestRate),
  ].filter((n): n is number => n != null)
}

/** 금액은 구조화 필드에 있어야 하고, 금액이 아닌 숫자는 인용한 quote 에 있어도 된다 (결정 g) */
const numbersOk = (text: string, allowed: number[], quoted: number[] = []) =>
  numbersIn(text).every(({ n, money }) => allowed.includes(n) || (!money && quoted.includes(n)))

/** 규칙 판정만으로 만드는 한 줄 요약. LLM 설명이 없어도 항상 존재한다 (명세 6-A) */
export const ruleHeadline = (v: MatchVerdict) =>
  ({
    '자격 충족': '입력하신 조건이 모두 지원 대상에 해당해요',
    '확인 필요': '입력하신 조건으로는 지금까지 어긋나는 부분이 없어요',
    조건부: '바꿀 수 있는 조건 하나가 맞지 않아요',
    '자격 미달': '지원 대상 조건이 맞지 않아요',
  })[v]

type Explanation = Pick<MatchResult, 'headline' | 'reasons' | 'cautions'>

export function validateMatch(
  exp: Explanation,
  ctx: { program: SupportProgram; verdict: MatchVerdict; rules: RuleResult[]; chunks: ProgramChunk[] },
): Explanation & { dropped: number } {
  if (ctx.verdict === '자격 미달') throw new Error(`자격 미달 공고는 결과에 올 수 없어요: ${ctx.program.id}`)
  const base = structuredNumbers(ctx.program)

  // 1) quote 가 해당 청크 원문에 그대로 있는가  2) 숫자가 구조화 필드 또는 인용한 quote 에 있는가
  const keep = (c: Explanation['reasons'][number]) => {
    const chunk = ctx.chunks.find((k) => k.id === c.chunkId && k.programId === ctx.program.id)
    const quote = normalizeText(c.quote)
    if (!chunk || !quote || !normalizeText(chunk.text).includes(quote)) return false
    return numbersOk(c.text, base, values(c.quote))
  }
  const reasons = exp.reasons.filter(keep)
  const cautions = exp.cautions.filter(keep)
  const headlineOk = numbersOk(exp.headline, base)
  const dropped =
    exp.reasons.length - reasons.length + (exp.cautions.length - cautions.length) + (headlineOk ? 0 : 1)
  if (dropped && import.meta.env?.DEV) console.warn(`[validateMatch] ${ctx.program.id}: ${dropped}개 문장 제거`)

  return {
    headline: headlineOk ? exp.headline : ruleHeadline(ctx.verdict),
    // 4) 남은 근거가 없으면 규칙 기반 문구. quote 는 수집 시 원문 검증을 거친 규칙 quote
    reasons: reasons.length
      ? reasons
      : ctx.rules
          .filter((x) => x.result === 'pass')
          .map((x) => ({ text: x.reason, quote: x.rule.quote, chunkId: '' })),
    cautions,
    dropped,
  }
}
