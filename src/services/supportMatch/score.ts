/* 매칭 점수·정렬 (명세 4-2, 결정 f). 서비스 자체 지표이며 같은 검색 결과 안에서의 상대 점수다 */

import { SCORE } from './config'
import type { MatchVerdict, RuleResult, SupportProgram, SupportType } from './types'

/** 후보가 SCORE.normalizeMinCandidates 이상이면 min-max 정규화, 아니면 원래 코사인 그대로 */
export function normalizeSimilarities(sims: number[]): number[] {
  if (sims.length < SCORE.normalizeMinCandidates) return sims
  const min = Math.min(...sims)
  const max = Math.max(...sims)
  return max === min ? sims : sims.map((s) => (s - min) / (max - min))
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n))

export function scoreMatch(i: {
  similarity: number
  rules: RuleResult[]
  needs: SupportType[]
  supportTypes: SupportType[]
}): number {
  const rules = i.rules.filter((x) => x.rule.kind !== 'other') // other 는 항상 unknown 이라 점수에서 뺀다
  const judged = rules.filter((x) => x.result !== 'unknown')
  const passRate = judged.length ? judged.filter((x) => x.result === 'pass').length / judged.length : 0.5
  const needsHit = i.needs.length === 0 ? 0.5 : i.needs.some((n) => i.supportTypes.includes(n)) ? 1 : 0
  const penalty = Math.min(SCORE.unknownPenalty * (rules.length - judged.length), SCORE.unknownPenaltyMax)
  const raw =
    SCORE.similarity * clamp01(i.similarity) + SCORE.passRate * passRate + SCORE.needs * needsHit - penalty
  return Math.round(Math.min(100, Math.max(0, raw)))
}

/** 마감까지 남은 일수. 연중·수시(rolling)거나 마감일이 없으면 null(상시 모집). 날짜는 'YYYY-MM-DD' */
export const daysLeft = (p: Pick<SupportProgram, 'applyEnd' | 'rolling'>, today: string) =>
  p.rolling || p.applyEnd == null ? null : Math.round((Date.parse(p.applyEnd) - Date.parse(today)) / 86_400_000)

const RANK: Record<MatchVerdict, number> = { '자격 충족': 0, '확인 필요': 1, 조건부: 2, '자격 미달': 3 }

/** 판정 등급(충족 > 확인 필요 > 조건부) → 매칭 점수 → 마감 임박(상시 모집은 뒤) */
export function sortResults<T extends { verdict: MatchVerdict; score: number; daysLeft: number | null }>(
  list: T[],
): T[] {
  return [...list].sort(
    (a, b) =>
      RANK[a.verdict] - RANK[b.verdict] ||
      b.score - a.score ||
      (a.daysLeft ?? Infinity) - (b.daysLeft ?? Infinity),
  )
}
