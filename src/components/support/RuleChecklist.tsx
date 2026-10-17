import { cx } from '@/lib/cx'
import { ageRange, shortSido } from '@/services/supportMatch/eligibility'
import type { DuplicatePolicy, EligibilityRule, RuleResult } from '@/services/supportMatch/types'

const LABEL: Record<EligibilityRule['kind'], string> = {
  age: '나이',
  region: '지역',
  bizStage: '창업 단계',
  industry: '업종',
  targetGroup: '지원 대상',
  other: '기타 조건',
}

// 판정은 기호 + 글자 + 색을 함께 쓴다 (색만으로 구분하지 않음)
const MARK = {
  pass: { sym: '✔', text: '충족', cls: 'text-pos' },
  fail: { sym: '✘', text: '미충족', cls: 'text-neg' },
  unknown: { sym: '?', text: '확인 필요', cls: 'text-muted' },
} as const

/** 공고 조건을 사람이 읽는 문장으로 */
function condition(r: EligibilityRule): string {
  switch (r.kind) {
    case 'age':
      return `${ageRange(r.min, r.max)} (만 나이 기준)`
    case 'region':
      return r.sido.length ? [r.sido.map(shortSido).join('·'), r.sigungu?.join('·')].filter(Boolean).join(' ') : '전국'
    case 'bizStage':
      return r.allowed.includes('예비창업') ? r.allowed.join(', ') : `사업자 등록 필요 (${r.allowed.join(', ')})`
    case 'industry':
      return [r.include?.length && `대상 ${r.include.join(', ')}`, r.exclude?.length && `제외 ${r.exclude.join(', ')}`]
        .filter(Boolean)
        .join(' / ')
    case 'targetGroup':
      return r.anyOf.join(', ')
    case 'other':
      return r.text
  }
}

// 카드(격자 한 칸) 안에 들어가도록 촘촘하게
const ROW = 'flex flex-col gap-0.5 px-2.5 py-2 text-[13px]'

/** 판정 기호 + 판정 글자 + 항목 + 조건 (한 덩어리로 붙여 쓴다) */
function Head({ mark, label, children }: { mark: (typeof MARK)[keyof typeof MARK]; label: string; children?: string }) {
  return (
    <span className="text-ink-soft">
      <span className={cx('mr-1.5 font-bold whitespace-nowrap', mark.cls)}>
        <span aria-hidden="true">{mark.sym}</span> {mark.text}
      </span>
      <span className="font-semibold text-ink">{label}</span> {children}
    </span>
  )
}

/** B. 조건 체크리스트: 규칙마다 판정 + 항목 + 공고 조건 한 줄씩 (명세 6-B).
    내 값·원문 인용·예외 조항은 화면을 깔끔하게 하려고 빼 두었다 (사용자 결정 2026-10-17) */
export function RuleChecklist({ rules, duplicatePolicy }: { rules: RuleResult[]; duplicatePolicy: DuplicatePolicy }) {
  return (
    // 카드 크기를 크게 바꾸지 않도록 높이를 제한하고 안에서 스크롤한다
    <ul className="flex max-h-64 flex-col divide-y divide-line overflow-y-auto rounded-panel border border-line bg-surface">
      {rules.map((x, i) => {
        const groupStart = x.group && rules[i - 1]?.group?.id !== x.group.id
        return (
          <li key={x.rule.kind + x.rule.quote} className={cx(ROW, x.group && 'pl-5')}>
            {groupStart && (
              <span className="-ml-2.5 font-bold text-muted">
                아래 조건 중 하나만 맞으면 돼요 · 그룹 판정 {MARK[x.group!.result].text}
              </span>
            )}
            <Head mark={MARK[x.result]} label={LABEL[x.rule.kind]}>
              {condition(x.rule)}
            </Head>
          </li>
        )
      })}
      <li className={ROW}>
        <span className="text-ink-soft">
          <span className="mr-1.5 font-bold text-muted">{duplicatePolicy.status}</span>
          <span className="font-semibold text-ink">중복 지원</span>
        </span>
      </li>
    </ul>
  )
}
