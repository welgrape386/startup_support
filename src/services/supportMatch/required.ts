import type { UserProfile } from './types'

/** 예비창업자 여부. 창업 단계가 정해져야 단계별 필수 항목이 정해진다 */
export function isPreStartup(p: UserProfile): boolean {
  return p.bizStage.value === '예비창업'
}

/**
 * 필수 입력값 (회의 결정: 기창업자 5개, 예비창업자 4개)
 * - 공통: 나이, 거주지 구, 창업 단계
 * - 기창업: 업력(개월), 사업장 구 추가
 * - 예비창업: 창업 예정 구 추가
 * 창업 단계를 모르면 공통 3개만 필수로 본다
 */
export function requiredFields(p: UserProfile): (keyof UserProfile)[] {
  const common: (keyof UserProfile)[] = ['age', 'sigungu', 'bizStage']
  if (!p.bizStage.value) return common
  return isPreStartup(p) ? [...common, 'bizSigungu'] : [...common, 'experienceMonths', 'bizSigungu']
}

function hasValue(p: UserProfile, k: keyof UserProfile): boolean {
  const f = p[k]
  return typeof f === 'object' && f !== null && 'value' in f && f.value != null && f.value !== ''
}

/** 빠진 필수 항목 (화면 나열과 "확인 필요" 표시에 쓴다) */
export function missingFields(p: UserProfile): (keyof UserProfile)[] {
  return requiredFields(p).filter((k) => !hasValue(p, k))
}

const LABEL: Partial<Record<keyof UserProfile, string>> = {
  age: '나이',
  sigungu: '거주지 구',
  bizStage: '창업 단계',
  experienceMonths: '업력(개월)',
}

/** 화면에 보이는 항목 이름. 사업장 구는 창업 단계에 따라 '창업 예정 구'가 된다 */
export function fieldLabel(k: keyof UserProfile, p: UserProfile): string {
  if (k === 'bizSigungu') return isPreStartup(p) ? '창업 예정 구' : '사업장 구'
  return LABEL[k] ?? String(k)
}
