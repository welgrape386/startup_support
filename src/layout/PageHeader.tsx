import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from '@/components/Icon'
import { cx } from '@/lib/cx'

export type Crumb = { label: string; to?: string }

function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav className="flex items-center gap-1.5 text-[13px] text-muted">
      {items.map((c, i) => (
        <span key={c.label} className="flex items-center gap-1.5">
          {i > 0 && <Icon name="chevron-right" size={12} />}
          {c.to ? (
            <Link to={c.to} className="hover:text-ink">
              {c.label}
            </Link>
          ) : (
            <span className={cx(i === items.length - 1 && 'text-ink-soft')}>{c.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}

/** 페이지 헤더 — 브레드크럼 + 큰 제목 + 설명 + (오른쪽 필터/버튼 슬롯) */
export function PageHeader({
  breadcrumb,
  title,
  description,
  right,
}: {
  breadcrumb?: Crumb[]
  title: string
  description?: ReactNode
  right?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-5">
      {breadcrumb && <Breadcrumb items={breadcrumb} />}
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <h1 className="text-[26px] leading-tight font-extrabold tracking-tight text-ink sm:text-[32px]">
            {title}
          </h1>
          {description && (
            <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted">
              {description}
            </p>
          )}
        </div>
        {right && <div className="shrink-0">{right}</div>}
      </div>
    </div>
  )
}
