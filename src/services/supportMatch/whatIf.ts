/* 한 걸음만 더 (명세 6-C, 결정 k·l). 조건부 공고에 대해 프로필 한 항목만 바꿔 규칙으로 다시 판정한다.
   LLM 을 쓰지 않는다. 정보 제공용이므로 라벨에 권유 표현("~하세요")을 쓰지 않는다. */

import { NEXT_STEPS_MAX } from './config'
import { isActionable, isOpen, judgeProgram, shortSido } from './eligibility'
import type { EligibilityRule, NextStep, SupportProgram, UserProfile } from './types'

type Candidate = Omit<NextStep, 'programIds' | 'unknownAfter'>

/** 후보 값은 공고 규칙에 적힌 값에서 가져온다. isActionable 이 true 인 규칙만 들어온다 */
function candidates(rule: EligibilityRule): Candidate[] {
  if (rule.kind === 'bizStage')
    // 예비창업 → 사업자 등록 직후(업력3년이하)면 사업자 단계 공고를 모두 충족한다
    return [{ field: 'bizStage', value: '업력3년이하', label: '사업자 등록을 하면', patch: { bizStage: '업력3년이하' } }]
  if (rule.kind === 'region')
    // 같은 시도 안의 시군구만 (isActionable 이 시도 일치를 보장)
    return (rule.sigungu ?? []).map((gu) => ({
      field: 'sigungu',
      value: gu,
      label: `사업장 소재지가 ${shortSido(rule.sido[0])} ${gu}이면`,
      patch: { sigungu: gu },
    }))
  return []
}

export function applyPatch(profile: UserProfile, patch: NextStep['patch']): UserProfile {
  const next: Record<string, unknown> = { ...profile }
  for (const [k, v] of Object.entries(patch)) next[k] = { value: v }
  return next as UserProfile
}

/** 모집 중인 조건부 공고 중, 한 항목만 바꾸면 충족·확인 필요가 되는 것을 (항목, 값)별로 묶는다 */
export function nextSteps(programs: SupportProgram[], profile: UserProfile, today: string): NextStep[] {
  const groups = new Map<string, NextStep>()
  for (const program of programs) {
    if (!isOpen(program, today)) continue
    const { verdict, rules } = judgeProgram(program, profile)
    if (verdict !== '조건부') continue
    for (const x of rules) {
      if (!isActionable(x, profile)) continue
      for (const c of candidates(x.rule)) {
        const after = judgeProgram(program, applyPatch(profile, c.patch))
        if (after.verdict !== '자격 충족' && after.verdict !== '확인 필요') continue
        const key = JSON.stringify(c.patch)
        const g = groups.get(key) ?? { ...c, programIds: [], unknownAfter: {} }
        g.programIds.push(program.id)
        g.unknownAfter[program.id] = after.rules.filter((r) => r.result === 'unknown').length
        groups.set(key, g)
      }
    }
  }
  // 공고 수 내림차순, 동점이면 묶음 안 1인 최대 금액이 큰 쪽. 금액이 없으면 0 으로 본다 (추정하지 않음)
  const amount = new Map(programs.map((p) => [p.id, p.amountMaxManwon ?? 0]))
  const maxAmount = (s: NextStep) => Math.max(...s.programIds.map((id) => amount.get(id) ?? 0))
  return [...groups.values()]
    .sort((a, b) => b.programIds.length - a.programIds.length || maxAmount(b) - maxAmount(a))
    .slice(0, NEXT_STEPS_MAX)
}
