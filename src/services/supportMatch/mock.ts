/* 개발용 샘플 공고 3건 (명세 3-1). 실제 공고가 아니다 → source:'mock', 화면에 "샘플 데이터" 라벨.
   회귀 체크와 Phase 3 의 API 키·인덱스 없음 폴백에서 쓴다. 마감일은 기준일(today)에서 상대값. */

import type { SupportProgram } from './types'

const addDays = (today: string, n: number) =>
  new Date(Date.parse(today) + n * 86_400_000).toISOString().slice(0, 10)

export function mockPrograms(today: string): SupportProgram[] {
  const base = {
    source: 'mock',
    status: '모집중',
    url: 'https://www.k-startup.go.kr',
    fetchedAt: today,
    reviewed: false,
    rolling: false,
    duplicatePolicy: { status: '미확인' },
  } as const
  return [
    {
      ...base,
      id: 'mock:youth-startup-fund',
      sourceId: 'youth-startup-fund',
      title: '청년전용창업자금',
      agency: '중소벤처기업진흥공단',
      supportTypes: ['융자'],
      amountMaxManwon: 10000,
      interestRate: '연 2.0% 고정(융자)',
      applyEnd: addDays(today, 12),
      summary: '만 19~34세 예비창업자 및 창업 3년 이내 기업',
      fields: { 지원대상: '만 19~34세 예비창업자 및 창업 3년 이내 기업' },
      eligibility: [{ mode: 'all', rules: [
        { kind: 'age', min: 19, max: 34, quote: '만 19~34세 예비창업자 및 창업 3년 이내 기업', section: '지원대상' },
        { kind: 'bizStage', allowed: ['예비창업', '업력3년이하'], quote: '만 19~34세 예비창업자 및 창업 3년 이내 기업', section: '지원대상' },
      ] }],
    },
    {
      ...base,
      id: 'mock:pre-startup-package',
      sourceId: 'pre-startup-package',
      title: '예비창업패키지',
      agency: '창업진흥원',
      supportTypes: ['보조금', '사업화'],
      amountMaxManwon: 5000,
      applyEnd: addDays(today, 5),
      summary: '만 19~39세, 업력 없는 예비창업자',
      fields: { 지원대상: '만 19~39세, 업력 없는 예비창업자' },
      eligibility: [{ mode: 'all', rules: [
        { kind: 'age', min: 19, max: 39, quote: '만 19~39세, 업력 없는 예비창업자', section: '지원대상' },
        { kind: 'bizStage', allowed: ['예비창업'], quote: '만 19~39세, 업력 없는 예비창업자', section: '지원대상' },
      ] }],
    },
    {
      ...base,
      id: 'mock:youth-startup-academy',
      sourceId: 'youth-startup-academy',
      title: '청년창업사관학교',
      agency: '중소벤처기업진흥공단',
      supportTypes: ['사업화', '멘토링', '교육'],
      amountMaxManwon: 10000,
      summary: '만 19~39세 청년 (예비)창업자',
      fields: { 지원대상: '만 19~39세 청년 (예비)창업자', 신청기간: '연중 수시' },
      rolling: true,
      eligibility: [{ mode: 'all', rules: [
        { kind: 'age', min: 19, max: 39, quote: '만 19~39세 청년 (예비)창업자', section: '지원대상' },
        { kind: 'bizStage', allowed: ['예비창업', '업력3년이하'], quote: '만 19~39세 청년 (예비)창업자', section: '지원대상' },
      ] }],
    },
  ]
}
