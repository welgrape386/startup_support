/* =========================================================================
   UI 확인용 placeholder 응답 (Phase 3 의 API 가 생기면 삭제 대상).
   판정·점수·한 걸음만 더는 Phase 1 의 실제 규칙 코드(eligibility·score·whatIf)를 그대로 쓴다.
   프로필은 LLM 없이 규칙 파서(parse.ts)로만 만들고, 의미 검색이 없으므로 유사도는 0 으로 둔다.
   meta.dataSource='mock' 이므로 화면에 "샘플 데이터" 라벨이 뜬다.
   ========================================================================= */

import { ruleProfile } from '@/lib/parse'
import { verifiedDuplicatePolicy, exceptionClauses } from './clauses'
import { kstDate, partition } from './eligibility'
import { mockPrograms } from './mock'
import { daysLeft, scoreMatch, sortResults } from './score'
import type {
  MatchResult,
  SupportMatchRequest,
  SupportMatchResponse,
  SupportProgram,
  UserProfile,
} from './types'
import { buildSummary, coverageOf } from './summary'
import { ruleHeadline } from './validate'
import { nextSteps } from './whatIf'

/** "한 걸음만 더" 화면 확인용 표본. data/raw/manual/incheon-samples.json 의 소상공인보증지원을
    data/eval/rule-gold.json 정답 규칙대로 옮긴 것 (mock 3건만으로는 조건부가 생기지 않음) */
const bojeungSample = (fetchedAt: string): SupportProgram => ({
  id: 'mock:incheon-sosang-bojeung',
  source: 'mock',
  portal: '인천시 혜택·지원',
  sourceId: 'incheon-sosang-bojeung',
  title: '소상공인보증지원',
  agency: '인천광역시',
  operator: '인천신용보증재단',
  supportTypes: ['보증'],
  totalBudgetText: '3,250억원',
  supportDetail: '이차보전 지원(연1.5~2%, 3년간)',
  applyStart: '2026-01-01',
  applyEnd: '2026-12-31',
  rolling: true,
  status: '모집중',
  // 공고 원문에 중복 수혜 문구가 없다
  duplicatePolicy: { status: '미확인' },
  eligibility: [{ mode: 'all', rules: [
    { kind: 'region', sido: ['인천광역시'], quote: '타시도 소상공인', section: '지원제외기준' },
    {
      kind: 'bizStage',
      allowed: ['업력3년이하', '업력7년이하', '기창업'],
      quote: '인천시에 사업자 등록을 한 소상공인',
      section: '지원조건',
    },
    { kind: 'targetGroup', anyOf: ['소상공인'], quote: '인천시에 사업장을 둔 소상공인', section: '지원대상' },
  ] }],
  summary: '담보력이 부족한 인천 소재 소상공인의 채무를 보증',
  url: 'https://www.incheon.go.kr/eco/ECO030201',
  contact: '소상공인정책과 / 인천신용보증재단 보증사업부/ 032-260-1543',
  // 포털 원문 항목 (incheon-samples.json 그대로). 요약의 주의 문장 quote 를 이 원문과 대조한다
  fields: {
    사업소개: '담보력이 부족한 인천 소재 소상공인의 채무를 보증함으로써 자금융통을 원활히 하여 소상공인 경영안정 도모',
    신청기간: '2026.1.1.~ 2026.12.31. (연중)',
    지원대상: '인천시에 사업장을 둔 소상공인(특례보증 별 상이)',
    지원규모: '3,250억원',
    지원내용: '소상공인 특례보증 및 이차보전 지원(연1.5~2%, 3년간)',
    지원조건: '인천시에 사업자 등록을 한 소상공인',
    지원제외기준: '타시도 소상공인',
  },
  fetchedAt,
  reviewed: true,
})

/** 신호등 탭 4종이 골고루 채워지는지 보려는 화면 확인용 가상 공고 (실제 공고 아님. 기관명·공고명·설명은 화면 확인용으로 임의로 붙였다).
    예시 입력(인천 예비창업 소상공인 / 서울 마포 카페 예비창업) 기준으로 탭마다 2~4건이 나오도록 조건을 나눴다.
    회귀 체크가 mock 3건에 의존하므로 mock.ts 가 아니라 여기에 둔다 */
// 기존 표본의 화면용 공고명 (실제 공고 제목처럼 보이게)
const SCREEN_TITLE: Record<string, string> = {
  'mock:youth-startup-fund': '2026년 청년전용창업자금 융자 지원 공고',
  'mock:pre-startup-package': '2026년 예비창업패키지 예비창업자 모집 공고',
  'mock:youth-startup-academy': '2026년 청년창업사관학교 입교생 모집 공고',
  'mock:incheon-sosang-bojeung': '2026년 인천 소상공인 특례보증 지원 공고',
}

function screenSamples(today: string): SupportProgram[] {
  const addDays = (n: number) => new Date(Date.parse(today) + n * 86_400_000).toISOString().slice(0, 10)
  type Rule = SupportProgram['eligibility'][number]['rules'][number]
  // 규칙 종류별로 quote·section 만 뺀 입력 (유니온마다 Omit)
  type RuleIn = Rule extends infer R ? (R extends Rule ? Omit<R, 'quote' | 'section'> : never) : never
  const s = (
    id: string,
    title: string,
    supportTypes: SupportProgram['supportTypes'],
    target: string,
    rules: RuleIn[],
    extra: Partial<SupportProgram> = {},
  ): SupportProgram => ({
    id: `mock:screen-${id}`,
    source: 'mock',
    sourceId: `screen-${id}`,
    title,
    agency: '',
    supportTypes,
    status: '모집중',
    applyEnd: addDays(20),
    rolling: false,
    duplicatePolicy: { status: '미확인' },
    summary: target,
    fields: { 지원대상: target },
    // 근거 quote 는 지원대상 원문 그대로
    eligibility: [{ mode: 'all', rules: rules.map((r) => ({ ...r, quote: target, section: '지원대상' }) as Rule) }],
    url: 'https://www.k-startup.go.kr',
    fetchedAt: today,
    reviewed: false,
    ...extra,
  })
  return [
    // 지금 신청 가능 (전국·인천 예비창업 / 서울 마포)
    s('youth-edu', '2026년 청년 창업 기초 교육과정 교육생 모집 공고', ['교육', '멘토링'], '만 19~39세 예비창업자 및 창업 3년 이내 대표자', [
      { kind: 'age', min: 19, max: 39 },
      { kind: 'bizStage', allowed: ['예비창업', '업력3년이하'] },
    ], { agency: '창업진흥원', summary: '사업계획서 작성부터 세무·노무까지 8주 과정 교육과 1:1 멘토링', applyEnd: addDays(9) }),
    s('incheon-space', '2026년 인천 예비창업자 공유오피스 입주기업 모집 공고', ['공간'], '인천광역시 소재 예비창업자', [
      { kind: 'region', sido: ['인천광역시'] },
      { kind: 'bizStage', allowed: ['예비창업'] },
    ], { agency: '인천창업지원센터', summary: '공유오피스 좌석을 최대 12개월 무상 제공하고 입주 중 창업 상담 지원', applyEnd: addDays(2) }),
    s('mapo-grant', '2026년 마포구 청년 창업 초기자금 지원사업 참여자 모집 공고', ['보조금'], '서울특별시 마포구 소재 만 19~39세 (예비)창업자', [
      { kind: 'region', sido: ['서울특별시'], sigungu: ['마포구'] },
      { kind: 'age', min: 19, max: 39 },
    ], { agency: '마포구청 일자리경제과', summary: '창업 초기 임차료·장비 구입비 등 사업화 비용 일부 지원', amountMaxManwon: 2000, applyEnd: addDays(15) }),
    // 조건부 가능 (사업자 등록 / 같은 시도 안 시군구)
    s('sosang-loan', '2026년 소상공인 경영개선 자금 지원사업 통합 공고', ['융자'], '사업자 등록을 한 소상공인', [
      { kind: 'bizStage', allowed: ['업력3년이하', '업력7년이하', '기창업'] },
      { kind: 'targetGroup', anyOf: ['소상공인'] },
    ], { agency: '소상공인시장진흥공단', summary: '시설 개선·운영 자금을 저금리로 융자하고 경영 진단 컨설팅 연계', amountMaxManwon: 7000, applyEnd: addDays(30) }),
    s('incheon-relocate', '2026년 인천 초기 창업기업 사업장 환경개선 지원 공고', ['보조금'], '인천광역시 소재 창업 3년 이내 기업', [
      { kind: 'region', sido: ['인천광역시'] },
      { kind: 'bizStage', allowed: ['업력3년이하'] },
    ], { agency: '인천경제산업정보테크노파크', summary: '간판·인테리어·안전설비 등 사업장 환경개선 비용 지원', amountMaxManwon: 1500, applyEnd: addDays(6) }),
    s('gangnam-space', '2026년 강남구 창업 공간 입주기업 모집 공고', ['공간'], '서울특별시 강남구 소재 예비창업자', [
      { kind: 'region', sido: ['서울특별시'], sigungu: ['강남구'] },
      { kind: 'bizStage', allowed: ['예비창업'] },
    ], { agency: '강남구 창업지원센터', summary: '독립 사무실과 회의실을 제공하고 투자 연계 프로그램 운영', applyEnd: addDays(11) }),
    // 확인 필요 (입력에 없는 정보·구조화 안 되는 조건)
    s('michuhol-space', '2026년 미추홀구 창업 공간 입주자 모집 공고', ['공간'], '인천광역시 미추홀구 소재 예비창업자', [
      { kind: 'region', sido: ['인천광역시'], sigungu: ['미추홀구'] },
      { kind: 'bizStage', allowed: ['예비창업'] },
    ], { agency: '미추홀구청 지역경제과', summary: '구 창업보육실 입주와 시제품 제작 비용 일부 지원', applyEnd: addDays(13) }),
    s('women-mentor', '2026년 여성 창업 멘토링 프로그램 참가자 모집 공고', ['멘토링'], '여성 예비창업자', [
      { kind: 'targetGroup', anyOf: ['여성'] },
      { kind: 'bizStage', allowed: ['예비창업'] },
    ], { agency: '여성기업종합지원센터', summary: '선배 여성 창업가와 6개월간 월 2회 멘토링, 판로 상담 제공', applyEnd: addDays(25) }),
    s('resident-edu', '2026년 지역 정착 창업 아카데미 수강생 모집 공고', ['교육'], '공고일 기준 해당 지역에 6개월 이상 거주한 예비창업자', [
      { kind: 'other', text: '공고일 기준 6개월 이상 거주' },
      { kind: 'bizStage', allowed: ['예비창업'] },
    ], { agency: '지역창업혁신센터', summary: '지역 상권 분석과 아이템 검증 중심의 10주 실전 교육', applyEnd: addDays(18) }),
    // 해당 안 됨 (나이·업종)
    s('middle-age', '2026년 중장년 재도전 창업 지원사업 모집 공고', ['보조금'], '만 40~64세 (예비)창업자', [
      { kind: 'age', min: 40, max: 64 },
    ], { agency: '중장년창업지원센터', summary: '경력 기반 창업을 준비하는 중장년에게 사업화 자금과 교육 지원', amountMaxManwon: 3000 }),
    s('tech-only', '2026년 광주 창업BuS 프로그램 창업기업 모집 공고', ['사업화'], '기술 기반 예비창업자 (음식점·카페 등 생활 업종 제외)', [
      { kind: 'industry', exclude: ['음식점', '카페'] },
      { kind: 'bizStage', allowed: ['예비창업'] },
    ], { agency: '광주창업지원허브', summary: '기술 아이템 시제품 제작과 투자 유치 준비를 단계별로 지원', amountMaxManwon: 10000, applyEnd: addDays(27) }),
  ]
}

export function buildUiPlaceholder(
  text: string,
  overrides: SupportMatchRequest['overrides'],
): SupportMatchResponse {
  const today = kstDate(new Date())
  const profile = ruleProfile(text, overrides)
  const programs = [...mockPrograms(today), bojeungSample(today), ...screenSamples(today)].map((p) => ({
    ...p,
    title: SCREEN_TITLE[p.id] ?? p.title,
  }))
  const { eligible, conditional, excluded, rejected } = partition(programs, profile, today)

  const toResult = ({ program, verdict, rules }: (typeof eligible)[number]): MatchResult => {
    const { eligibility: _, ...rest } = program
    return {
      program: { ...rest, duplicatePolicy: verifiedDuplicatePolicy(program) },
      verdict,
      // 의미 검색이 없으므로(Phase 3) 유사도 0. 규칙 충족률·니즈 일치만 반영된다
      score: scoreMatch({ similarity: 0, rules, needs: profile.needs, supportTypes: program.supportTypes }),
      rules,
      headline: ruleHeadline(verdict),
      reasons: rules
        .filter((x) => x.result === 'pass')
        .map((x) => ({ text: x.reason, quote: x.rule.quote, chunkId: '' })),
      cautions: [],
      exceptions: exceptionClauses(program),
      daysLeft: daysLeft(program, today),
    }
  }

  const missing: (keyof UserProfile)[] = []
  if (profile.age.value == null) missing.push('age')
  if (!profile.sido.value) missing.push('sido')
  if (!profile.bizStage.value) missing.push('bizStage')
  if (!profile.industryCategory.value) missing.push('industryCategory')

  const results = sortResults(eligible.map(toResult))
  const conditionalResults = sortResults(conditional.map(toResult))
  return {
    profile,
    missing,
    results,
    conditional: conditionalResults,
    excluded,
    nextSteps: nextSteps(programs, profile, today),
    summary: buildSummary({ results, conditional: conditionalResults, rejected, profile }),
    coverage: coverageOf(programs),
    meta: {
      dataSource: 'mock',
      parser: 'rule',
      indexBuiltAt: today,
      totalPrograms: programs.length,
      droppedClaims: 0,
    },
  }
}
