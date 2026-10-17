import { cx } from '@/lib/cx'
import { Icon, type IconName } from './Icon'

type Kind = 'self' | 'estimate'

const MAP: Record<Kind, { label: string; icon: IconName; cls: string }> = {
  self: { label: '서비스 자체 분석 지표', icon: 'target', cls: 'bg-primary-50 text-primary-700' },
  estimate: { label: '데이터 기반 추정치', icon: 'trend', cls: 'bg-pos-soft text-pos' },
}

/** 공식 지표가 아님을 명시하는 라벨 (원칙 3: 자체 지표는 자체 지표라고 표시) */
export function DataBadge({ kind, className }: { kind: Kind; className?: string }) {
  const m = MAP[kind]
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-chip px-2 py-1 text-[13px] font-semibold',
        m.cls,
        className,
      )}
    >
      <Icon name={m.icon} size={12} />
      {m.label}
    </span>
  )
}
