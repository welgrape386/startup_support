/* 자격 판정 (명세 4-1·6-A, 결정 a~e·k). 구조화된 규칙만 비교한다.
   공고 본문(summary·청크)은 읽지 않으므로 본문 속 인젝션이 판정에 영향을 줄 수 없다. */

import type {
  BizStage,
  EligibilityRule,
  MatchVerdict,
  RuleResult,
  SupportMatchResponse,
  SupportProgram,
  TargetGroup,
  UserProfile,
} from './types'

/** asOf 시각의 한국 날짜 'YYYY-MM-DD' */
export const kstDate = (asOf: Date) => new Date(asOf.getTime() + 9 * 3_600_000).toISOString().slice(0, 10)

/** 판정 기준일 고정 (나애 요청 2026-11-12: 공고 데이터 기준일 10/16). 오늘 날짜로 되돌리려면 kstDate(new Date()) */
export const JUDGE_DATE = '2026-10-16'

/** 모집중·모집예정이고 마감일이 today 이후(당일 포함). applyEnd 는 'YYYY-MM-DD' */
export const isOpen = (p: SupportProgram, today: string) =>
  p.status !== '마감' && (p.applyEnd == null || p.applyEnd >= today)

export const shortSido = (s: string) => s.replace(/(특별시|광역시|특별자치시|특별자치도)$/, '')

// 업력 포함 관계: 업력3년이하 ⊂ 업력7년이하 ⊂ 기창업. 예비창업은 별개
const TENURE: Partial<Record<BizStage, number>> = { 업력3년이하: 1, 업력7년이하: 2, 기창업: 3 }

const normIndustry = (s: string) => s.replace(/\s/g, '').replace(/업$/, '')

// 나이만으로 판정 가능한 대상 그룹. 나머지(여성·장애인 등)는 사용자가 밝히지 않으면 unknown
const BY_AGE: Partial<Record<TargetGroup, (age: number) => boolean>> = {
  청년: (a) => a <= 39,
  중장년: (a) => a >= 40,
}

export const ageRange = (min?: number, max?: number) =>
  min != null && max != null
    ? `만 ${min}~${max}세`
    : max != null
      ? `만 ${max}세 이하`
      : min != null
        ? `만 ${min}세 이상`
        : '나이 제한 없음'

export function judgeRule(rule: EligibilityRule, profile: UserProfile): RuleResult {
  const r = (result: RuleResult['result'], reason: string): RuleResult => ({ rule, result, reason })
  switch (rule.kind) {
    case 'age': {
      const age = profile.age.value
      if (rule.min == null && rule.max == null) return r('pass', '나이 제한이 없어요')
      if (age == null) return r('unknown', '나이를 입력하지 않았어요')
      if (rule.max != null && age > rule.max) return r('fail', `만 ${rule.max}세 초과`)
      if (rule.min != null && age < rule.min) return r('fail', `만 ${rule.min}세 미만`)
      return r('pass', `${ageRange(rule.min, rule.max)} 대상인데 ${age}세라 해당돼요`)
    }
    case 'region': {
      if (rule.sido.length === 0) return r('pass', '전국 대상 공고예요')
      const area = rule.sido.map(shortSido).join('·')
      const sido = profile.sido.value
      if (!sido) return r('unknown', `${area} 지역 공고라 지역 확인이 필요해요`)
      if (!rule.sido.includes(sido)) return r('fail', `${area} 지역 한정 공고예요`)
      if (!rule.sigungu?.length) return r('pass', `${area} 지역 공고예요`)
      const gu = profile.sigungu.value
      const guArea = rule.sigungu.join('·')
      if (!gu) return r('unknown', `${guArea} 한정 공고라 시군구 확인이 필요해요`)
      return rule.sigungu.includes(gu)
        ? r('pass', `${guArea} 지역 공고예요`)
        : r('fail', `${guArea} 지역 한정 공고예요`)
    }
    case 'bizStage': {
      const stage = profile.bizStage.value
      const allowed = rule.allowed.join(', ')
      if (!stage) return r('unknown', '창업 단계를 입력하지 않았어요')
      if (rule.allowed.includes(stage)) return r('pass', `${stage} 단계가 지원 대상에 포함돼요`)
      const mine = TENURE[stage]
      const ranks = rule.allowed.map((s) => TENURE[s]).filter((n): n is number => n != null)
      if (mine != null && ranks.some((n) => n > mine))
        return r('pass', `${stage} 단계는 지원 대상(${allowed})에 포함돼요`)
      if (mine != null && ranks.length)
        return r('unknown', `지원 대상(${allowed})에 해당하는지 정확한 업력 확인이 필요해요`)
      return r('fail', `${stage} 단계는 지원 대상(${allowed})이 아니에요`)
    }
    case 'industry': {
      const cat = profile.industryCategory.value
      if (!cat) return r('unknown', '업종을 입력하지 않았어요')
      const c = normIndustry(cat)
      const has = (xs?: string[]) => xs?.some((x) => normIndustry(x) === c)
      if (has(rule.exclude)) return r('fail', `${cat} 업종은 지원 제외 대상이에요`)
      if (!rule.include?.length || has(rule.include)) return r('pass', `${cat} 업종이 지원 대상에 해당돼요`)
      return r('unknown', `${cat} 업종이 지원 업종(${rule.include.join(', ')})에 포함되는지 확인이 필요해요`)
    }
    case 'targetGroup': {
      const groups = rule.anyOf.join('·')
      const age = profile.age.value
      if (
        rule.anyOf.includes('전체') ||
        rule.anyOf.some((g) => profile.targetGroups.includes(g) || (age != null && BY_AGE[g]?.(age)))
      )
        return r('pass', `${groups} 대상에 해당돼요`)
      if (age != null && rule.anyOf.every((g) => BY_AGE[g])) return r('fail', `${groups} 대상이 아니에요`)
      return r('unknown', `${groups} 대상인지 확인이 필요해요`)
    }
    case 'other':
      return r('unknown', `${rule.text} — 공고 원문을 직접 확인하세요`)
  }
}

/** "한 걸음"으로 풀 수 있는 fail 인가 (명세 6-C, 결정 k). 두 가지뿐이다:
    예비창업자의 사업자 등록, 같은 시도 안에서 시군구만 다른 경우.
    시도가 다르거나 업종·나이·대상 그룹·other 로 어긋나면 해당 안 됨 */
export function isActionable(x: RuleResult, profile: UserProfile): boolean {
  const { rule } = x
  if (x.result !== 'fail') return false
  if (rule.kind === 'region')
    return !!rule.sigungu?.length && rule.sido.length === 1 && rule.sido[0] === profile.sido.value
  if (rule.kind === 'bizStage')
    return profile.bizStage.value === '예비창업' && rule.allowed.some((s) => TENURE[s] != null)
  return false
}

/** 공고의 모든 규칙 (그룹 무시) */
export const allRules = (p: SupportProgram) => p.eligibility.flatMap((g) => g.rules)

/** 실제로 공고를 막는 fail 인가. any 그룹 안의 fail 은 그룹 전체가 fail 일 때만 */
export const isBlocking = (x: RuleResult) => x.result === 'fail' && (x.group?.result ?? 'fail') === 'fail'

/** any 그룹: 하나라도 pass → pass, 전부 fail → fail, 그 외 unknown */
function anyResult(rs: RuleResult[]): RuleResult['result'] {
  if (rs.some((x) => x.result === 'pass')) return 'pass'
  return rs.length && rs.every((x) => x.result === 'fail') ? 'fail' : 'unknown'
}

/** 판정 단위로 묶어 등급을 낸다 (명세 4-1·4-1a). all 그룹은 규칙 하나가 한 단위, any 그룹은 그룹 하나가 한 단위.
    fail 0: unknown(other 포함) 있으면 확인 필요, 없으면 자격 충족.
    fail 단위 1개이고 바꿀 수 있으면 조건부, 그 외 자격 미달 */
export function judgeProgram(program: SupportProgram, profile: UserProfile) {
  const rules: RuleResult[] = []
  const units: { result: RuleResult['result']; actionable: boolean }[] = []
  program.eligibility.forEach((g, id) => {
    const rs = g.rules.map((rule) => judgeRule(rule, profile))
    if (g.mode === 'all') {
      rules.push(...rs)
      for (const x of rs) units.push({ result: x.result, actionable: isActionable(x, profile) })
      return
    }
    const result = anyResult(rs)
    rules.push(...rs.map((x) => ({ ...x, group: { id, result } })))
    units.push({ result, actionable: rs.some((x) => isActionable(x, profile)) })
  })
  const fails = units.filter((u) => u.result === 'fail')
  const verdict: MatchVerdict =
    fails.length === 0
      ? units.some((u) => u.result === 'unknown')
        ? '확인 필요'
        : '자격 충족'
      : fails.length === 1 && fails[0].actionable
        ? '조건부'
        : '자격 미달'
  return { verdict, rules }
}

/** 조건부 공고의 사유: 개업(사업자 등록) 또는 사업장 소재지(시군구). 조건부가 아니면 null.
    공고마다 하나만 고르므로 사유별 집계가 서로 겹치지 않는다 */
export function conditionalField(rules: RuleResult[], profile: UserProfile): 'bizStage' | 'sigungu' | null {
  const x = rules.find((r) => isBlocking(r) && isActionable(r, profile))
  return x ? (x.rule.kind === 'bizStage' ? 'bizStage' : 'sigungu') : null
}

/** 마감 공고는 버리고 셋으로 나눈다. eligible(충족·확인 필요)만 추천 목록(results)이 된다.
    conditional(조건부)은 "한 걸음만 더" 영역, excluded(자격 미달)는 사유 목록.
    rejected 는 excluded 와 같은 공고를 규칙 판정과 함께 담는다 (요약의 주의 문장용) */
export function partition(programs: SupportProgram[], profile: UserProfile, today: string) {
  type Judged = { program: SupportProgram } & ReturnType<typeof judgeProgram>
  const eligible: Judged[] = []
  const conditional: Judged[] = []
  const excluded: SupportMatchResponse['excluded'] = []
  const rejected: Judged[] = []
  for (const program of programs) {
    if (!isOpen(program, today)) continue
    const j = judgeProgram(program, profile)
    if (j.verdict === '자격 미달') {
      rejected.push({ program, ...j })
      excluded.push({
        programId: program.id,
        title: program.title,
        failedReasons: j.rules.filter(isBlocking).map((x) => x.reason),
      })
    } else (j.verdict === '조건부' ? conditional : eligible).push({ program, ...j })
  }
  return { eligible, conditional, excluded, rejected }
}
