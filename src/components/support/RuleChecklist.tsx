import { cx } from '@/lib/cx'
import { ageRange, shortSido } from '@/services/supportMatch/eligibility'
import type { EligibilityRule, RuleResult } from '@/services/supportMatch/types'

const LABEL: Record<EligibilityRule['kind'], string> = {
  age: '나이',
  region: '지역',
  bizStage: '창업 단계',
  industry: '업종',
  targetGroup: '지원 대상',
  other: '기타 조건',
}

// 결과는 기호 + 글자 + 색을 함께 쓴다 (색만으로 구분하지 않음)
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

/** 나이·지역·창업 단계·업종은 공고 조건이 아직 없어도 줄을 보여준다 (공고 조건은 확인 필요) */
const SHOWN_KINDS: EligibilityRule['kind'][] = ['age', 'region', 'bizStage', 'industry']

// 카드(격자 한 칸) 안에 들어가도록 촘촘하게. 왼쪽은 항목·조건, 오른쪽은 결과
const ROW = 'flex items-start justify-between gap-3 px-2.5 py-2 text-[13px]'

/** 한 줄: 왼쪽 항목 + 공고 조건, 오른쪽 결과 (충족 / 미충족 / 확인 필요) */
function Row({ mark, label, indent, children }: { mark: (typeof MARK)[keyof typeof MARK]; label: string; indent?: boolean; children: string }) {
  return (
    <div className={cx(ROW, indent && 'pl-5')}>
      <span className="min-w-0 text-ink-soft">
        <span className="font-semibold text-ink">{label}</span> {children}
      </span>
      <span className={cx('shrink-0 font-bold whitespace-nowrap', mark.cls)}>
        <span aria-hidden="true">{mark.sym}</span> {mark.text}
      </span>
    </div>
  )
}

/** B. 조건 체크리스트: 규칙마다 항목 · 공고 조건 · 결과 한 줄씩 (명세 6-B).
    내 입력·원문 인용·예외 조항은 화면을 깔끔하게 하려고 빼 두었다 */
export function RuleChecklist({ rules }: { rules: RuleResult[] }) {
  return (
    // 카드 크기를 크게 바꾸지 않도록 높이를 제한하고 안에서 스크롤한다
    <ul className="flex max-h-64 flex-col divide-y divide-line overflow-y-auto rounded-panel border border-line bg-surface">
      {SHOWN_KINDS.filter((k) => !rules.some((x) => x.rule.kind === k)).map((k) => (
        <li key={'missing-' + k}>
          <Row mark={MARK.unknown} label={LABEL[k]}>공고 조건 확인 필요</Row>
        </li>
      ))}
      {rules.map((x, i) => {
        const groupStart = x.group && rules[i - 1]?.group?.id !== x.group.id
        return (
          <li key={x.rule.kind + x.rule.quote}>
            {groupStart && (
              <span className="block px-2.5 pt-2 font-bold text-muted">
                아래 조건 중 하나만 맞으면 돼요 · 그룹 판정 {MARK[x.group!.result].text}
              </span>
            )}
            <Row mark={MARK[x.result]} label={LABEL[x.rule.kind]} indent={!!x.group}>
              {condition(x.rule)}
            </Row>
          </li>
        )
      })}
    </ul>
  )
}
