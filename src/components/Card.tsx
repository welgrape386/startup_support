import type { HTMLAttributes } from 'react'
import { cx } from '@/lib/cx'

type CardProps = HTMLAttributes<HTMLDivElement> & {
  /** 기본 내부 여백 사용 여부 (지도/차트처럼 꽉 채우는 경우 false) */
  padded?: boolean
}

/** 공통 카드 — 흰 배경 + 1px 라인 + 아주 얕은 shadow (DESIGN.md 6) */
export function Card({ className, padded = true, ...rest }: CardProps) {
  return (
    <div
      className={cx(
        'rounded-card border border-line bg-surface shadow-card',
        padded && 'p-6 sm:p-7',
        className,
      )}
      {...rest}
    />
  )
}
