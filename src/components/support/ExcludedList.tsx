import { Card } from '@/components/Card'
import type { SupportMatchResponse } from '@/services/supportMatch/types'
import { VerdictBadge } from './MatchCard'

/** 자격 미달로 제외된 공고와 사유. "해당 안 됨" 탭 안에서 항상 펼쳐 보여준다 (탭이 접힘 역할) */
export function ExcludedList({ items }: { items: SupportMatchResponse['excluded'] }) {
  return (
    <Card>
      <ul className="flex flex-col divide-y divide-line">
        {items.map((x) => (
          <li key={x.programId} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0">
            <span className="flex flex-wrap items-center gap-2">
              <VerdictBadge verdict="자격 미달" />
              <span className="text-sm font-semibold text-ink">{x.title}</span>
            </span>
            <span className="text-sm text-neg">{x.failedReasons.join(' · ')}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
