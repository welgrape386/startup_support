/* 지원사업 매칭 공용 타입 (명세 3-2, 3-4, 5장). 클라이언트·서버 공용 */

export type SupportType = '융자' | '보조금' | '보증' | '교육' | '멘토링' | '공간' | '사업화' | '기타'

/** 결과 화면 카테고리 필터. 순서·표기 그대로 버튼에 쓴다 (공고의 support_types 값) */
export const CATEGORIES = ['자금', '교육·컨설팅', '공간·시설', '홍보·판매', '인력', '기술개발', '해외진출', '제도·인증', '기타'] as const
export type Category = (typeof CATEGORIES)[number]
export type BizStage = '예비창업' | '업력3년이하' | '업력7년이하' | '기창업'
export type TargetGroup = '청년' | '여성' | '장애인' | '중장년' | '소상공인' | '재창업' | '전체'

/** 근거가 나온 포털 항목 (명세 3-2a) */
export type RuleSection = '지원대상' | '지원조건' | '지원제외기준' | '기타'

/** 자격 조건 하나. 공고 원문 근거(quote)와 출처 항목(section)을 반드시 같이 저장한다 */
export type EligibilityRule = { quote: string; section: RuleSection } & (
  | { kind: 'age'; min?: number; max?: number }
  | { kind: 'region'; sido: string[]; sigungu?: string[] } // 빈 배열 = 전국
  | { kind: 'bizStage'; allowed: BizStage[] }
  | { kind: 'industry'; include?: string[]; exclude?: string[] }
  | { kind: 'targetGroup'; anyOf: TargetGroup[] }
  | { kind: 'other'; text: string } // 구조화 불가 → 항상 unknown
)

/** 규칙 그룹 (명세 4-1a). all = 모두 충족, any = 하나라도 충족("A 또는 B").
    공고는 그룹 배열을 가지며 그룹끼리는 모두 충족해야 한다. 기본은 all 그룹 하나 */
export type RuleGroup = { mode: 'all' | 'any'; rules: EligibilityRule[] }

/** 중복 수혜 제한 (명세 3-2b). 원문에 문구가 있을 때만 가능·불가·조건부, 없으면 반드시 미확인.
    section 은 quote 가 나온 포털 항목 이름(fields 의 키) */
export type DuplicatePolicy =
  | { status: '가능' | '불가' | '조건부'; quote: string; section: string }
  | { status: '미확인' }

/** 규칙으로 바꾸지 않은 예외 문구 (명세 6-B). 판정에 쓰지 않고 체크리스트에 '?'로만 보여준다 */
export type ExceptionClause = { quote: string; section: string }

export type SupportProgram = {
  id: string
  source: 'manual' | 'kstartup' | 'bizinfo' | 'mock'
  /** 수동 수집한 포털 이름 (예: '인천시 혜택·지원'). 수집 범위 표시에 쓴다 */
  portal?: string
  sourceId: string
  title: string
  agency: string
  operator?: string
  supportTypes: SupportType[]
  /** 카테고리 (여러 개 가능). API 필드명 그대로. 없으면 카테고리 필터에 걸리지 않는다 */
  support_types?: Category[]
  /** 1인(1건)당 한도만. 포털 '지원규모'(사업 전체 예산)는 넣지 않는다 */
  amountMaxManwon?: number
  /** 사업 전체 예산 원문 (표시 전용, 점수·검증 근거로 쓰지 않음) */
  totalBudgetText?: string
  interestRate?: string
  /** 이차보전 등 금리가 아닌 지원 조건 원문 */
  supportDetail?: string
  applyStart?: string
  applyEnd?: string
  /** 연중·수시 모집 → daysLeft=null, "상시 모집" */
  rolling: boolean
  status: '모집중' | '모집예정' | '마감'
  eligibility: RuleGroup[]
  duplicatePolicy: DuplicatePolicy
  summary: string
  url: string
  contact?: string
  /** 신청 사이트 URL (기업마당 외 별도 신청 페이지가 있을 때) */
  applyUrl?: string                       // TODO: API 필드
  /** 제출 서류 목록 */
  submissionDocs?: string[]               // TODO: API 필드
  /** 우대·가산점 항목 */
  bonusPoints?: string[]                  // TODO: API 필드
  /** 첨부 파일 (공고 원문 PDF/HWP 등) */
  attachmentFiles?: { name: string; url: string }[]  // TODO: API 필드
  /** 차수형 모집 일정 */
  rounds?: { round: string; start: string; end: string; status: '접수중' | '마감' | '예정' }[]  // TODO: API 필드
  /** 포털 원문 항목 그대로 (quote 검증 대상) */
  fields: Record<string, string>
  fetchedAt: string
  reviewed: boolean
}

export type ProgramChunk = {
  id: string
  programId: string
  section: '지원대상' | '지원내용' | '신청방법' | '기타'
  text: string
  embedding: number[]
}

export type Extracted<T> = { value: T | null; evidence?: string }

export type UserProfile = {
  age: Extracted<number>
  sido: Extracted<string>
  sigungu: Extracted<string>
  bizStage: Extracted<BizStage>
  industryCategory: Extracted<string>
  industryText: Extracted<string>
  targetGroups: TargetGroup[]
  needs: SupportType[]
  fundingGapManwon: Extracted<number>
  budgetManwon: Extracted<number>
  experienceYears: Extracted<number>
  freeText: string
}

export type SupportMatchRequest = {
  text: string
  overrides?: Partial<Record<keyof UserProfile, unknown>>
}

export type MatchVerdict = '자격 충족' | '확인 필요' | '조건부' | '자격 미달'
export type RuleResult = {
  rule: EligibilityRule
  result: 'pass' | 'fail' | 'unknown'
  reason: string
  /** any 그룹에 속한 규칙이면 그룹 번호와 그룹 판정. 이 규칙이 fail 이어도 그룹이 pass 면 걸리지 않는다 */
  group?: { id: number; result: 'pass' | 'fail' | 'unknown' }
}

export type MatchResult = {
  program: Omit<SupportProgram, 'eligibility'>
  verdict: MatchVerdict
  score: number
  rules: RuleResult[]
  headline: string
  reasons: { text: string; quote: string; chunkId: string }[]
  cautions: { text: string; quote: string; chunkId: string }[]
  /** 예외 조항 (판정에 반영하지 않음) */
  exceptions: ExceptionClause[]
  daysLeft: number | null
}

export type SupportMatchResponse = {
  profile: UserProfile
  missing: (keyof UserProfile)[]
  /** 추천 목록. 자격 충족·확인 필요만 (평가 하네스의 "추천"도 이것만, 명세 7장) */
  results: MatchResult[]
  /** 조건부 공고. "한 걸음만 더" 영역에만 표시하고 추천으로 세지 않는다 */
  conditional: MatchResult[]
  excluded: { programId: string; title: string; failedReasons: string[] }[]
  nextSteps: NextStep[]
  /** 결과 상단 요약 (명세 6-D). 숫자·날짜·quote 는 전부 판정 결과에서 계산한다 */
  summary: MatchSummary
  /** 수집 범위 (명세 6-F) */
  coverage: Coverage
  meta: {
    dataSource: 'live' | 'mock'
    parser: 'llm' | 'rule'
    indexBuiltAt: string
    totalPrograms: number
    droppedClaims: number
  }
}

/** 한 걸음만 더 (명세 6-C). 사업자 등록 또는 같은 시도 안 시군구만 patch 로 바꿔 재판정한 결과 */
export type NextStep = {
  field: 'bizStage' | 'sigungu'
  value: string
  label: string
  patch: Partial<Record<'bizStage' | 'sigungu', string>>
  programIds: string[]
  /** 공고별, 바꾼 뒤에도 남는 unknown 규칙 수 */
  unknownAfter: Record<string, number>
}

export type MatchSummary = {
  eligibleCount: number
  checkCount: number
  /** 조건부 공고를 사유별로 나눈 수. 공고마다 사유가 하나라 겹치지 않는다 (합 = conditional 길이) */
  conditional: { bizStage: number; sigungu: number }
  /** 추천(results) 중 마감이 가장 급한 공고. 상시 모집(rolling)은 제외 */
  urgent: { programId: string; title: string; daysLeft: number; applyEnd: string } | null
  /** 해당 안 됨 사유 중 근거 quote 가 공고 원문 대조를 통과한 것 하나 */
  caution: { programId: string; title: string; quote: string; section: RuleSection } | null
}

export type Coverage = {
  sources: { portal: string; count: number }[]
  total: number
  /** 수집 기준일 중 가장 최근 */
  asOf: string | null
  /** 수집한 지역 한정 공고의 시도 목록 (전국 공고는 포함하지 않음) */
  regions: string[]
}

export type SupportMatchError = {
  error: {
    code: 'INVALID_INPUT' | 'LLM_UNAVAILABLE' | 'INDEX_MISSING' | 'INTERNAL'
    message: string
  }
}
