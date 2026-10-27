import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { Badge } from '@/components/Badge'
import { Button, buttonClasses } from '@/components/Button'
import { Card } from '@/components/Card'
import { Icon } from '@/components/Icon'
import { ExcludedList } from '@/components/support/ExcludedList'
import { MatchCard } from '@/components/support/MatchCard'
import { ProfileChips } from '@/components/support/ProfileChips'
import { ResultSummary } from '@/components/support/ResultSummary'
import { cx } from '@/lib/cx'
import { Container } from '@/layout/Container'
import { PageHeader } from '@/layout/PageHeader'
import { fetchResultSummary, fetchSupportMatch, SupportMatchApiError } from '@/services/supportMatch/client'
import {
  CATEGORIES,
  type Category,
  type MatchResult,
  type SupportMatchRequest,
  type SupportMatchResponse,
  type UserProfile,
} from '@/services/supportMatch/types'
import { loadInput, saveInput } from '@/lib/supportMatchInput'
import { Analyzing, SignalLight, SignalSummaryBar, type Verdict } from '../../SignalComponents2'

type Sort = 'recommend' | 'deadline'

// 결과 화면 상단 배치 순서: 이렇게 이해했어요 → AI 요약. 순서는 여기서만 바꾼다
const TOP_ORDER = ['profile', 'summary'] as const

// 필터·정렬 선택은 남색(ink). 판정색·브랜드 파랑과 선택 상태가 섞이지 않게 한다
const tabCls = (active: boolean) =>
  cx(
    'min-h-10 rounded-chip px-3 text-[13px] font-semibold transition-colors',
    active ? 'bg-ink text-white' : 'bg-bg-soft text-muted hover:bg-primary-50',
  )
const groupLabel = 'mr-1 text-[13px] font-semibold text-muted'

// green → yellow → unknown → red 순서
const SIGNAL_GROUPS: { signal: Verdict; label: string }[] = [
  { signal: 'green', label: '지금 신청 가능' },
  { signal: 'yellow', label: '조건부 가능' },
  { signal: 'unknown', label: '확인 필요' },
  { signal: 'red', label: '해당 안 됨' },
]

const RAIL_LABEL_COLOR: Record<Verdict, string> = {
  green: 'var(--green-text)',
  yellow: 'var(--yellow-text)',
  unknown: 'var(--body)',
  red: 'var(--red-text)',
}

/** /support-match/results — 입력 화면에서 저장한 문장으로 판정 결과를 보여준다 */
export function SupportMatchResults() {
  const location = useLocation()
  const [req, setReq] = useState<SupportMatchRequest | null>(
    () => loadInput() ?? (location.state as SupportMatchRequest | null),
  )
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [step, setStep] = useState(0)
  const [res, setRes] = useState<SupportMatchResponse | null>(null)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  // 비어 있으면 전체. 여러 개 고르면 하나라도 붙은 공고를 보여준다(OR)
  const [categories, setCategories] = useState<Category[]>([])
  const [aiSummary, setAiSummary] = useState<Awaited<ReturnType<typeof fetchResultSummary>> | null>(null)
  const [sort, setSort] = useState<Sort>('recommend')
  const [signalFilter, setSignalFilter] = useState<Verdict | 'all'>('all')

  // 입력(문장·칩 수정)이 바뀔 때마다 다시 요청. 늦게 도착한 이전 응답은 버린다
  useEffect(() => {
    if (!req) return
    let alive = true
    setStatus('loading')
    setError(null)
    setSignalFilter('all')
    fetchSupportMatch(req).then(
      (data) => {
        if (!alive) return
        setRes(data)
        setStatus('success')
      },
      (e) => {
        if (!alive) return
        const err = e instanceof SupportMatchApiError ? e : null
        setError({ code: err?.code ?? 'INTERNAL', message: err?.message ?? '잠시 후 다시 시도해주세요.' })
        setStatus('error')
      },
    )
    return () => {
      alive = false
    }
  }, [req])

  // 결과가 바뀌면 3줄 요약도 다시 받는다. 실패하면 요약 상자만 숨긴다
  useEffect(() => {
    setAiSummary(null)
    if (!res) return
    let alive = true
    fetchResultSummary(res).then(
      (s) => alive && setAiSummary(s),
      () => {},
    )
    return () => {
      alive = false
    }
  }, [res])

  // 로딩 단계 (표시용 타이머)
  useEffect(() => {
    if (status !== 'loading') return
    setStep(0)
    const id = window.setInterval(() => setStep((s) => Math.min(s + 1, 3)), 900)
    return () => window.clearInterval(id)
  }, [status])

  // 신호등 4가지 건수: green=자격충족 / yellow=조건부 / unknown=확인필요 / red=해당안됨
  const signalCounts = res ? {
    green: res.results.filter((r) => r.verdict === '자격 충족').length,
    yellow: res.conditional.length,
    unknown: res.results.filter((r) => r.verdict === '확인 필요').length,
    red: res.excluded.length,
  } : null

  // 그룹별 필터·정렬 적용 결과 (red는 excluded 그대로)
  const groupedItems = useMemo(() => {
    if (!res) return null
    const applyFS = (items: MatchResult[]) => {
      const list = items.filter(
        (r) => categories.length === 0 || (r.program.support_types ?? []).some((t) => categories.includes(t)),
      )
      return sort === 'deadline'
        ? [...list].sort((a, b) => (a.daysLeft ?? Infinity) - (b.daysLeft ?? Infinity))
        : list
    }
    return {
      green: applyFS(res.results.filter((r) => r.verdict === '자격 충족')),
      yellow: applyFS(res.conditional),
      unknown: applyFS(res.results.filter((r) => r.verdict === '확인 필요')),
      red: res.excluded,
    }
  }, [res, categories, sort])

  const toggleCategory = (c: Category) =>
    setCategories((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]))

  if (!req) return <Navigate to="/support-match" replace />

  const onOverride = (patch: Partial<Record<keyof UserProfile, unknown>>) => {
    const next = { ...req, overrides: { ...req.overrides, ...patch } }
    saveInput(next)
    setReq(next)
  }

  const ageUnknownCount =
    res?.results.filter((r) => r.rules.some((x) => x.rule.kind === 'age' && x.result === 'unknown'))
      .length ?? 0

  const totalCount =
    (res?.results.length ?? 0) + (res?.conditional.length ?? 0) + (res?.excluded.length ?? 0)

  return (
    <Container className="flex flex-col gap-6 py-page-y">
      <PageHeader
        breadcrumb={[{ label: '홈', to: '/' }, { label: '지원사업 찾기', to: '/support-match' }, { label: '결과' }]}
        title="판정 결과"
        right={
          <Link to="/support-match" className={buttonClasses('secondary', 'md')}>
            조건 다시 입력
          </Link>
        }
      />

      <div className="flex flex-col gap-6" aria-live="polite">
        {status === 'loading' && <Analyzing step={Math.min(step, 2)} />}

        {status === 'error' && error && (
          <Card className="flex flex-col items-start gap-3">
            <p className="text-sm text-neg">{error.message}</p>
            {import.meta.env.DEV && <p className="text-xs text-faint">code: {error.code}</p>}
            <Button variant="secondary" onClick={() => setReq({ ...req })}>
              다시 시도
            </Button>
          </Card>
        )}

        {status === 'success' && res && (
          <>
            {/* 샘플 데이터 표시(띠·카드 배지)는 사용자 결정으로 임시 생략 (원칙 4 예외, CLAUDE.md 현재 상태 참고) */}
            {/* 상단 카드 두 개는 16px 간격으로 묶는다 */}
            <div className="flex flex-col gap-4">
              {TOP_ORDER.map((k) =>
                k === 'summary' ? (
                  // 결과 전체 AI 3줄 요약 (공고가 0건이면 숨김)
                  totalCount > 0 && aiSummary && <ResultSummary key={k} lines={aiSummary.lines} />
                ) : (
                  <div key={k} id="profile-chips" className="scroll-mt-6">
                    <ProfileChips
                      text={req.text}
                      profile={res.profile}
                      missing={res.missing}
                      onOverride={onOverride}
                    />
                  </div>
                ),
              )}
            </div>

            {/* 모집 중 공고 자체가 0건일 때만 */}
            {totalCount === 0 ? (
              <Card className="flex flex-col gap-3">
                <p className="text-[15px] font-bold text-ink">조건에 맞는 모집 중 공고가 없어요</p>
                <p className="text-sm text-muted">지역이나 창업 단계 조건을 바꿔서 다시 찾아보세요.</p>
              </Card>
            ) : (
              <>
                {/* 신호등 요약 바 (4칸: green→yellow→unknown→red) */}
                <SignalSummaryBar
                  counts={signalCounts!}
                  activeFilter={signalFilter}
                  setActiveFilter={setSignalFilter}
                />

                {/* 자격 충족·조건부 가능이 모두 0건일 때 안내 */}
                {signalCounts && signalCounts.green + signalCounts.yellow === 0 && (
                  <div
                    role="status"
                    className="flex items-start gap-2 rounded-panel bg-info-soft px-4 py-3 text-sm text-ink-soft"
                  >
                    <Icon name="info" size={16} className="mt-0.5 shrink-0 text-primary-600" />
                    <span className="flex flex-col items-start gap-1">
                      <span>
                        <span className="font-semibold text-ink">조건을 수정해보세요.</span> 지금 신청 가능한 공고가 없어요.
                        위 &lsquo;이렇게 이해했어요&rsquo;의 칩을 눌러 나이·지역·창업 단계를 고치고 저장하면 다시 판정해요.
                      </span>
                      <button
                        type="button"
                        onClick={() => document.getElementById('profile-chips')?.scrollIntoView({ behavior: 'smooth' })}
                        className="inline-flex min-h-10 items-center gap-1 font-semibold text-primary-600"
                      >
                        조건 수정하러 가기
                        <Icon name="arrow-right" size={14} />
                      </button>
                    </span>
                  </div>
                )}

                {/* 유형·정렬 필터 바 */}
                <Card className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="카테고리 (여러 개 선택 가능)">
                    <span aria-hidden="true" className={groupLabel}>카테고리</span>
                    <button
                      type="button"
                      aria-pressed={categories.length === 0}
                      onClick={() => setCategories([])}
                      className={tabCls(categories.length === 0)}
                    >
                      전체
                    </button>
                    {/* 0건인 카테고리도 숨기지 않는다 */}
                    {CATEGORIES.map((c) => (
                      <button
                        key={c}
                        type="button"
                        aria-pressed={categories.includes(c)}
                        onClick={() => toggleCategory(c)}
                        className={tabCls(categories.includes(c))}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="정렬">
                    <span aria-hidden="true" className={groupLabel}>정렬</span>
                    <button
                      type="button"
                      aria-pressed={sort === 'recommend'}
                      onClick={() => setSort('recommend')}
                      className={tabCls(sort === 'recommend')}
                    >
                      추천순
                    </button>
                    <button
                      type="button"
                      aria-pressed={sort === 'deadline'}
                      onClick={() => setSort('deadline')}
                      className={tabCls(sort === 'deadline')}
                    >
                      마감 임박순
                    </button>
                  </div>
                </Card>

                {/* 신호등 그룹별 카드 */}
                <div className="flex flex-col gap-9">
                  {SIGNAL_GROUPS.map(({ signal, label }) => {
                    const count = signalCounts![signal]
                    if (count === 0) return null
                    if (signalFilter !== 'all' && signalFilter !== signal) return null

                    const isRed = signal === 'red'
                    const matchItems = isRed
                      ? []
                      : (groupedItems![signal as Exclude<Verdict, 'red'>] as MatchResult[])

                    return (
                      <div key={signal} className={`signal-group signal-group--${signal}`}>
                        {/* 왼쪽 레일: 신호등 + 이름 + 건수 */}
                        <div className="signal-group__rail">
                          <div className="signal-group__rail-inner">
                            <SignalLight size="card" verdict={signal} />
                            <p className="text-center text-xs font-semibold" style={{ color: RAIL_LABEL_COLOR[signal] }}>{label}</p>
                            <p className="text-center text-xs text-muted">{count}건</p>
                          </div>
                        </div>

                        {/* 오른쪽 패널: 카드 그리드 */}
                        <div className="signal-group__panel">
                          {isRed ? (
                            <ExcludedList items={res.excluded} />
                          ) : (
                            <>
                              {signal === 'unknown' && ageUnknownCount > 0 && (
                                <p className="mb-3 text-[13px] text-warn">
                                  나이를 알려주시면 {ageUnknownCount}건을 더 정확히 판정할 수 있어요.
                                </p>
                              )}
                              {matchItems.length === 0 ? (
                                <p className="text-sm text-muted">이 카테고리에 해당하는 공고가 없어요. 다른 카테고리를 확인해보세요.</p>
                              ) : (
                                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                                  {matchItems.map((r) => (
                                    <MatchCard key={r.program.id} result={r} profile={res.profile} />
                                  ))}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            )}

            {res.meta.parser === 'rule' && res.meta.dataSource === 'live' && (
              <Badge tone="warn">간이 해석으로 판정한 결과예요</Badge>
            )}
          </>
        )}
      </div>
    </Container>
  )
}
