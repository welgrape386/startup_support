import type { KeyboardEvent, ReactNode } from 'react'
import type { IconName } from '@/components/Icon'
import { cx } from '@/lib/cx'
import type { MatchVerdict } from '@/services/supportMatch/types'

export type VerdictTab = 'eligible' | 'conditional' | 'check' | 'excluded'

/** 신호등 탭 라벨·아이콘·색·안내는 여기 한 곳에서만 바꾼다. 카드 상태 라벨도 이 label 을 쓴다.
    color = 비활성 탭 숫자 색, on = 선택한 탭 배경·글자·테두리 색 (연한 판정색 채움 + 2px 판정색 테두리).
    확인 필요는 연한 색이 탭 바와 같은 회색이라 흰 배경 */
export const VERDICT_TABS: {
  key: VerdictTab
  verdict: MatchVerdict
  label: string
  icon: IconName
  color: string
  on: string
  empty: string
}[] = [
  { key: 'eligible', verdict: '자격 충족', label: '지금 신청 가능', icon: 'check-circle', color: 'text-pos', on: 'bg-pos-soft text-pos ring-pos', empty: '지금 자격을 모두 충족하는 공고가 없어요.' },
  { key: 'conditional', verdict: '조건부', label: '조건부 가능', icon: 'half-circle', color: 'text-warn', on: 'bg-warn-soft text-warn ring-warn', empty: '조건 하나만 다른 공고가 없어요.' },
  { key: 'check', verdict: '확인 필요', label: '확인 필요', icon: 'question', color: 'text-muted', on: 'bg-surface text-muted ring-muted', empty: '확인이 필요한 공고가 없어요.' },
  { key: 'excluded', verdict: '자격 미달', label: '해당 안 됨', icon: 'x', color: 'text-neg', on: 'bg-neg-soft text-neg ring-neg', empty: '자격이 안 맞아 제외된 공고가 없어요.' },
]

export const tabOf = (verdict: MatchVerdict) => VERDICT_TABS.find((t) => t.verdict === verdict)!

/** 조건부 가능 카드의 세부 라벨 (conditionalField 값별). applyThenRegister 는 데이터가 생기면 쓴다 (지금은 화면에 내지 않음) */
export const CONDITIONAL_SUBLABEL = {
  bizStage: '[개업 후 신청]',
  sigungu: '[소재지 조건]',
  applyThenRegister: '[신청 후 등록]',
} as const

/** 탭 순서대로 처음 비어 있지 않은 탭. 모두 비면 첫 탭 */
export function defaultTab(counts: Record<VerdictTab, number>): VerdictTab {
  return VERDICT_TABS.find((t) => counts[t.key] > 0)?.key ?? VERDICT_TABS[0].key
}

/** A. 신호등 탭 (명세 6-1). 선택한 탭의 패널만 렌더한다. 탭 바는 스크롤해도 위에 고정된다 */
export function VerdictTabs({
  counts,
  active,
  onChange,
  children,
}: {
  counts: Record<VerdictTab, number>
  active: VerdictTab
  onChange: (tab: VerdictTab) => void
  children: ReactNode
}) {
  // 좌우 화살표로 탭 이동 (roving tabindex)
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    e.preventDefault()
    const i = VERDICT_TABS.findIndex((t) => t.key === active)
    const next = VERDICT_TABS[(i + step + VERDICT_TABS.length) % VERDICT_TABS.length].key
    onChange(next)
    e.currentTarget.querySelector<HTMLButtonElement>(`#verdict-tab-${next}`)?.focus()
  }

  return (
    <div className="flex flex-col gap-3">
      {/* 앱 헤더는 고정이 아니라 top-0. 본문과 같은 불투명 배경으로 아래 카드가 비치지 않게 한다.
          모바일(2×2)은 탭 바가 화면을 많이 가려 고정하지 않는다 */}
      <div className="z-20 -mx-1 bg-surface px-1 py-2 sm:sticky sm:top-0">
        {/* 세그먼트: 연회색 바 안에 탭 4개. 선택한 탭만 연한 판정색 채움 + 2px 판정색 테두리 + 판정색 굵은 글자.
            비활성 탭은 라벨 + 판정색 숫자 (판정은 라벨 글자로도 구분된다) */}
        <div
          role="tablist"
          aria-label="판정 결과"
          onKeyDown={onKeyDown}
          className="grid grid-cols-2 gap-1 rounded-panel bg-bg-soft p-1 sm:grid-cols-4 sm:rounded-chip"
        >
          {VERDICT_TABS.map((t) => {
            const selected = t.key === active
            const empty = counts[t.key] === 0
            return (
              <button
                key={t.key}
                id={`verdict-tab-${t.key}`}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls="verdict-panel"
                tabIndex={selected ? 0 : -1}
                onClick={() => onChange(t.key)}
                className={cx(
                  'flex min-h-11 items-center justify-center gap-1.5 rounded-btn px-3 text-sm font-semibold whitespace-nowrap transition-colors duration-150 sm:rounded-chip',
                  selected ? cx(t.on, 'font-bold shadow-card ring-2 ring-inset') : cx('hover:text-ink', empty ? 'text-muted' : 'text-ink-soft'),
                )}
              >
                {t.label}
                {/* 비활성 0건 탭은 숫자도 흐리게 */}
                <span className={cx('font-bold tnum', !selected && (empty ? 'text-muted' : t.color))}>{counts[t.key]}</span>
              </button>
            )
          })}
        </div>
      </div>
      <div
        role="tabpanel"
        id="verdict-panel"
        aria-labelledby={`verdict-tab-${active}`}
        className="flex flex-col gap-4"
      >
        {children}
      </div>
    </div>
  )
}
