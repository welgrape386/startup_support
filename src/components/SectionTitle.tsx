import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'
import { Icon, type IconName } from './Icon'

/** 카드 내부 섹션 제목 (16~18px / 700) */
export function SectionTitle({
  children,
  icon,
  right,
  className,
}: {
  children: ReactNode
  icon?: IconName
  right?: ReactNode
  className?: string
}) {
  return (
    <div className={cx('flex items-center justify-between gap-3', className)}>
      <div className="flex items-center gap-2">
        {icon && (
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary-50 text-primary-600">
            <Icon name={icon} size={16} />
          </span>
        )}
        <h3 className="text-[17px] font-bold text-ink">{children}</h3>
      </div>
      {right}
    </div>
  )
}
