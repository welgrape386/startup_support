import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'

type Tone = 'pos' | 'neg' | 'warn' | 'info' | 'neutral' | 'violet'

// pos·neg 는 옅은 배경 위 대비가 4.5:1 에 못 미쳐(4.50·4.23) 흰 배경 + 테두리로 둔다 (흰 배경 5.02·4.83)
const TONE: Record<Tone, string> = {
  pos: 'border border-pos bg-surface text-pos',
  neg: 'border border-neg bg-surface text-neg',
  warn: 'bg-warn-soft text-warn',
  info: 'bg-info-soft text-primary-600',
  neutral: 'bg-bg-soft text-muted',
  violet: 'bg-[#f1ecfe] text-[#7c3aed]',
}

/** 상태 뱃지 — 옅은 배경 + 의미색 텍스트 (DESIGN.md 5) */
export function Badge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-chip px-2.5 py-1 text-[13px] font-semibold whitespace-nowrap',
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
