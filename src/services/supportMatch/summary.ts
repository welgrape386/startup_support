/* 결과 상단 요약·수집 범위 (명세 6-D, 6-F). LLM 없이 판정 결과에서 계산한다.
   화면 문장은 UI 가 템플릿으로 만들고, 여기서는 숫자·날짜·근거만 고른다 */

import { allRules, conditionalField, isBlocking } from './eligibility'
import type {
  Coverage,
  MatchResult,
  MatchSummary,
  RuleResult,
  SupportMatchResponse,
  SupportProgram,
  UserProfile,
} from './types'
import { normalizeText, numbersIn } from './validate'

/** quote 가 공고 원문 항목(fields)에 그대로 있는가 */
export function quoteInSource(p: SupportProgram, quote: string): boolean {
  const q = normalizeText(quote)
  return !!q && Object.values(p.fields).some((v) => normalizeText(v).includes(q))
}

export function buildSummary(i: {
  results: MatchResult[]
  conditional: MatchResult[]
  rejected: { program: SupportProgram; rules: RuleResult[] }[]
  profile: UserProfile
}): MatchSummary {
  const urgent = i.results
    .filter((r) => r.daysLeft != null && r.daysLeft >= 0 && r.program.applyEnd)
    .sort((a, b) => a.daysLeft! - b.daysLeft!)[0]

  let caution: MatchSummary['caution'] = null
  for (const { program, rules } of i.rejected) {
    const f = rules.find((x) => isBlocking(x) && quoteInSource(program, x.rule.quote))
    if (f) {
      caution = { programId: program.id, title: program.title, quote: f.rule.quote, section: f.rule.section }
      break
    }
  }

  return {
    eligibleCount: i.results.filter((r) => r.verdict === '자격 충족').length,
    checkCount: i.results.filter((r) => r.verdict === '확인 필요').length,
    // 구간이 겹치지 않도록 공고마다 사유 하나로만 센다
    conditional: {
      bizStage: i.conditional.filter((r) => conditionalField(r.rules, i.profile) === 'bizStage').length,
      sigungu: i.conditional.filter((r) => conditionalField(r.rules, i.profile) === 'sigungu').length,
    },
    urgent: urgent
      ? { programId: urgent.program.id, title: urgent.program.title, daysLeft: urgent.daysLeft!, applyEnd: urgent.program.applyEnd! }
      : null,
    caution,
  }
}

export function coverageOf(programs: SupportProgram[]): Coverage {
  const count = new Map<string, number>()
  for (const p of programs) count.set(p.portal ?? '샘플', (count.get(p.portal ?? '샘플') ?? 0) + 1)
  const regions = new Set(
    programs.flatMap((p) => allRules(p).flatMap((r) => (r.kind === 'region' ? r.sido : []))),
  )
  return {
    sources: [...count].map(([portal, n]) => ({ portal, count: n })),
    total: programs.length,
    asOf: programs.map((p) => p.fetchedAt.slice(0, 10)).sort().at(-1) ?? null,
    regions: [...regions],
  }
}

/** 결과 전체 3줄 요약 검증 (원칙 5). 문장 속 숫자가 판정 결과(건수·요약·D-day·1인 한도·마감일)에 없으면 그 문장은 버린다.
    ponytail: 숫자만 대조한다. 공고명·인용문 대조가 필요해지면 quoteInSource 로 넓힌다 */
export function verifiedSummaryLines(lines: string[], res: SupportMatchResponse): string[] {
  const shown = [...res.results, ...res.conditional]
  const allowed = [
    res.results.length,
    res.conditional.length,
    res.excluded.length,
    ...numbersIn(JSON.stringify(res.summary)).map((x) => x.n),
    ...shown.flatMap((r) => [r.daysLeft, r.program.amountMaxManwon, ...numbersIn(r.program.applyEnd ?? '').map((x) => x.n)]),
  ]
  return lines.filter((l) => numbersIn(l).every(({ n }) => allowed.includes(n))).slice(0, 3)
}
