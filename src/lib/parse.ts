/* 자유문장에서 값을 뽑는 간이 규칙 파서. LLM 실패 시 폴백이자 LLM 결과 교차검증용 (Phase 3에서 확장) */

import type {
  BizStage,
  SupportMatchRequest,
  SupportType,
  TargetGroup,
  UserProfile,
} from '@/services/supportMatch/types'

/** "29살", "만 36세" → 나이. 언급이 없거나 범위 밖이면 null */
export function extractAge(text: string): number | null {
  const m = text.match(/(만\s*)?(\d{2})\s*[살세]/)
  if (!m) return null
  const age = parseInt(m[2], 10)
  return age >= 14 && age <= 100 ? age : null
}

/** "3천만원", "1.5억", "500만원" → 만원 단위 정수. 없으면 null */
export function extractManwon(text: string): number | null {
  const eok = text.match(/(\d+(?:\.\d+)?)\s*억/)
  if (eok) return Math.round(parseFloat(eok[1]) * 10000)
  const cheon = text.match(/(\d+(?:\.\d+)?)\s*천\s*만/)
  if (cheon) return Math.round(parseFloat(cheon[1]) * 1000)
  const man = text.match(/(\d[\d,]*)\s*만\s*원?/)
  if (man) return parseInt(man[1].replace(/,/g, ''), 10)
  return null
}

const SIDO: [RegExp, string][] = [
  [/서울/, '서울특별시'],
  [/경기/, '경기도'],
  [/인천/, '인천광역시'],
  [/부산/, '부산광역시'],
  [/대구/, '대구광역시'],
  [/대전/, '대전광역시'],
  [/광주/, '광주광역시'],
  [/울산/, '울산광역시'],
  [/세종/, '세종특별자치시'],
  [/강원/, '강원특별자치도'],
  [/충북|충청북/, '충청북도'],
  [/충남|충청남/, '충청남도'],
  [/전북|전라북/, '전북특별자치도'],
  [/전남|전라남/, '전라남도'],
  [/경북|경상북/, '경상북도'],
  [/경남|경상남/, '경상남도'],
  [/제주/, '제주특별자치도'],
]

export function extractRegion(text: string): { sido: string | null; sigungu: string | null } {
  const sido = SIDO.find(([re]) => re.test(text))?.[1] ?? null
  const gu = text.match(/([가-힣]{1,4}[구군])(?=[에서의은는이가도\s,.]|$)/)?.[1] ?? null
  return { sido, sigungu: gu }
}

export function extractCategory(text: string): string | null {
  // 9개 업종 카테고리(src/lib/industry.ts)로 묶는다. 애매하면 비운다 (확인 필요)
  if (/카페|커피|베이커리|디저트\s*카페/.test(text)) return '음식·카페'
  if (/음식점|식당|한식|중식|일식|양식|분식|치킨|피자|고깃집|주점/.test(text)) return '음식·카페'
  return null
}

/** 업력을 개월로. "업력 2년", "3개월 차" 같은 명시된 표현만 읽는다 (추정하지 않음) */
export function extractExperienceMonths(text: string): number | null {
  const m = text.match(/업력\s*(\d+)\s*(개월|년)/) ?? text.match(/(\d+)\s*(개월|년)\s*(째|차|된|운영|영업)/)
  if (!m) return null
  return m[2] === '년' ? Number(m[1]) * 12 : Number(m[1])
}

const BIZ_PLACE = '사업장|영업장|매장|가게|점포|카페|식당|음식점'
/** 사업장(가게)과 같은 문장에 붙은 구만 읽는다. 거주지 구와 섞이지 않도록 장소 단어가 있을 때만 */
export function extractBizGu(text: string): string | null {
  const m = text.match(new RegExp(`(?:${BIZ_PLACE})[^.\\n]{0,15}?([가-힣]{1,4}구)|([가-힣]{1,4}구)[^.\\n]{0,15}?(?:${BIZ_PLACE})`))
  return m ? (m[1] ?? m[2] ?? null) : null
}

/** 규칙만으로 만든 프로필 (LLM 없음). 입력 화면의 실시간 칩과 샘플 응답이 같이 쓴다 */
export function ruleProfile(raw: string, overrides: SupportMatchRequest['overrides']): UserProfile {
  // 초안의 빈칸([나이], [예비창업자/사업자] 등)은 사용자가 쓴 정보가 아니므로 읽지 않는다
  const text = raw.replace(/\[[^\]]*\]/g, ' ')
  const o = overrides ?? {}
  const region = extractRegion(text)
  const age = (o.age as number | undefined) ?? extractAge(text)
  const sido = (o.sido as string | undefined) ?? region.sido
  const targetGroups: TargetGroup[] = []
  if (age != null && age <= 39) targetGroups.push('청년')
  if (/소상공인|자영업/.test(text)) targetGroups.push('소상공인')
  const needs: SupportType[] = []
  if (/모자라|부족|자금|대출|지원금/.test(text)) needs.push('융자', '보조금')
  if (/교육/.test(text)) needs.push('교육')
  if (/멘토링/.test(text)) needs.push('멘토링')
  return {
    age: { value: age },
    sido: { value: sido },
    // 칩으로 고친 시군구가 우선. 시도만 고치면 문장 속 시군구는 더 이상 맞지 않을 수 있으므로 비운다
    sigungu: { value: 'sigungu' in o ? ((o.sigungu as string | null) ?? null) : o.sido ? null : region.sigungu },
    bizStage: { value: (o.bizStage as BizStage | undefined) ?? (/예비/.test(text) ? '예비창업' : null) },
    industryCategory: { value: (o.industryCategory as string | undefined) ?? extractCategory(text) },
    industryText: { value: null },
    targetGroups,
    needs,
    fundingGapManwon: { value: extractManwon(text) },
    budgetManwon: { value: null },
    experienceYears: { value: null },
    // 예비창업자는 업력이 무조건 0개월 (회의 결정)
    experienceMonths: { value: 'experienceMonths' in o ? ((o.experienceMonths as number | null) ?? null) : (o.bizStage ?? (/예비/.test(text) ? '예비창업' : null)) === '예비창업' ? 0 : extractExperienceMonths(text) },
    // 칩으로 고친 사업장 구가 우선. 시도만 고치면 문장 속 구는 비운다 (시군구와 같은 규칙)
    bizSigungu: { value: 'bizSigungu' in o ? ((o.bizSigungu as string | null) ?? null) : o.sido ? null : extractBizGu(text) },
    freeText: raw,
  }
}
