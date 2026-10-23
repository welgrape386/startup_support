import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@/components/Badge'
import { Card } from '@/components/Card'
import { Icon } from '@/components/Icon'
import { cx } from '@/lib/cx'
import { conditionalField } from '@/services/supportMatch/eligibility'
import type { MatchResult, MatchVerdict, UserProfile } from '@/services/supportMatch/types'
import { RuleChecklist } from './RuleChecklist'
import { CONDITIONAL_SUBLABEL, tabOf } from './VerdictTabs'

const won = (m: number) =>
  m >= 10000 ? `${(m / 10000).toFixed(1).replace(/\.0$/, '')}억원` : `${m.toLocaleString()}만원`

// D-day 는 모양을 고정한다. 공통 Badge 가 바뀌어도 따라가지 않도록 클래스를 여기 둔다
const DAY_BASE = 'inline-flex items-center rounded-chip px-2.5 py-1 text-xs font-semibold whitespace-nowrap'
function DayBadge({ daysLeft }: { daysLeft: number | null }) {
  const [cls, text] =
    daysLeft == null
      ? ['bg-info-soft text-primary-600', '상시 모집']
      : daysLeft <= 3
        ? ['bg-neg-soft text-neg', `D-${daysLeft}`]
        : daysLeft <= 7
          ? ['bg-warn-soft text-warn', `D-${daysLeft}`]
          : ['bg-bg-soft text-muted', `D-${daysLeft}`]
  return <span className={cx(DAY_BASE, cls)}>{text}</span>
}

// A. 신호등 4종 (명세 6-A). 라벨은 VerdictTabs 상수를 함께 쓴다. head = 카드 상단 판정 헤더 색 (글자 대비 4.7 이상)
const VERDICT: Record<MatchVerdict, { tone: 'pos' | 'neutral' | 'warn' | 'neg'; head: string }> = {
  '자격 충족': { tone: 'pos', head: 'bg-pos-soft text-pos' },
  '확인 필요': { tone: 'neutral', head: 'bg-bg-soft text-muted' },
  조건부: { tone: 'warn', head: 'bg-warn-soft text-warn' },
  '자격 미달': { tone: 'neg', head: 'bg-neg-soft text-neg' },
}

export function VerdictBadge({ verdict }: { verdict: MatchVerdict }) {
  const t = tabOf(verdict)
  return (
    <Badge tone={VERDICT[verdict].tone}>
      <Icon name={t.icon} size={13} className="mr-1" />
      {t.label}
    </Badge>
  )
}

export function MatchCard({ result: r, profile }: { result: MatchResult; profile: UserProfile }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const p = r.program
  const cField = r.verdict === '조건부' ? conditionalField(r.rules, profile) : null
  const dup = p.duplicatePolicy
  // 수행기관이 있으면 수행기관을 먼저 보여준다
  const meta = [p.operator ?? p.agency, p.amountMaxManwon != null ? `1인 최대 ${won(p.amountMaxManwon)}` : null].filter(
    Boolean,
  )

  const goDetail = () => navigate(`/support-match/${p.id}`, { state: { result: r } })

  return (
    // 격자 안 카드. 체크리스트는 이 카드 안에서 펼친다 (높이 제한 + 안쪽 스크롤)
    <Card
      padded={false}
      className="flex flex-col overflow-hidden cursor-pointer transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
      role="link"
      tabIndex={0}
      onClick={goDetail}
      onKeyDown={(e) => { if (e.key === 'Enter') goDetail() }}
    >
      {/* 판정 헤더: 판정색 연한 배경 + 글자 라벨 */}
      <div className={cx('flex min-h-11 items-center gap-2 px-6 text-sm font-bold', VERDICT[r.verdict].head)}>
        {tabOf(r.verdict).label}
        {cField && <span className="font-semibold">{CONDITIONAL_SUBLABEL[cField]}</span>}
      </div>
      <div className="flex flex-1 flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <DayBadge daysLeft={r.daysLeft} />
          {p.supportTypes.map((t) => (
            <Badge key={t} tone={t === '융자' ? 'violet' : 'info'}>
              {t}
            </Badge>
          ))}
          <Badge tone={dup.status === '불가' ? 'warn' : 'neutral'}>중복 지원 {dup.status}</Badge>
        </div>

        {/* 배지 줄과 공고명 사이를 조금 더 띄운다 */}
        <div className="mt-1">
          <h3 className="text-[17px] leading-snug font-bold text-ink">{p.title}</h3>
          <p className="mt-1.5 text-[13px] text-muted">{meta.join(' · ')}</p>
        </div>

        {/* 공고마다 같은 판정 문구(headline) 대신 공고 데이터의 사업 요약을 보여준다 */}
        {p.summary && <p className="text-sm leading-relaxed text-ink-soft">{p.summary}</p>}

        {/* 링크는 카드 맨 아래에 붙여 같은 줄 카드끼리 위치를 맞춘다 */}
        <div className="mt-auto flex flex-wrap items-center gap-x-5 gap-y-2">
          <a
            href={p.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-primary-600"
            onClick={(e) => e.stopPropagation()}
          >
            공고 원문 보기
            <Icon name="arrow-right" size={14} />
          </a>
          <button
            type="button"
            aria-expanded={open}
            onClick={(e) => { e.stopPropagation(); setOpen((v) => !v) }}
            className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-muted"
          >
            조건 체크리스트
            <Icon name={open ? 'chevron-down' : 'chevron-right'} size={14} />
          </button>
        </div>

        {open && (
          <RuleChecklist rules={r.rules} duplicatePolicy={dup} />
        )}
      </div>
    </Card>
  )
}
