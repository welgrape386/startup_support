import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { Badge } from '@/components/Badge'
import { Button, buttonClasses } from '@/components/Button'
import { Card } from '@/components/Card'
import { Icon } from '@/components/Icon'
import { ExcludedList } from '@/components/support/ExcludedList'
import { MatchCard } from '@/components/support/MatchCard'
import { ProfileChips } from '@/components/support/ProfileChips'
import { defaultTab, VERDICT_TABS, type VerdictTab, VerdictTabs } from '@/components/support/VerdictTabs'
import { cx } from '@/lib/cx'
import { Container } from '@/layout/Container'
import { PageHeader } from '@/layout/PageHeader'
import { fetchSupportMatch, SupportMatchApiError } from '@/services/supportMatch/client'
import type { SupportMatchRequest, SupportMatchResponse, UserProfile } from '@/services/supportMatch/types'
import { loadInput, saveInput } from '@/lib/supportMatchInput'

const LOADING_STEPS = ['조건 분석 중', '공고 검색 중', '자격 판정 중', '근거 검증 중']

type Filter = 'all' | 'money' | 'edu' | 'space'
type Sort = 'recommend' | 'deadline'

const FILTERS: { key: Filter; label: string; types: string[] }[] = [
  { key: 'all', label: '전체', types: [] },
  { key: 'money', label: '자금', types: ['융자', '보조금', '사업화'] },
  { key: 'edu', label: '교육·멘토링', types: ['교육', '멘토링'] },
  { key: 'space', label: '공간', types: ['공간'] },
]

// 필터·정렬 선택은 남색(ink). 판정색(초록·주황·빨강)·브랜드 파랑과 선택 상태가 섞이지 않게 한다
const tabCls = (active: boolean) =>
  cx(
    'min-h-10 rounded-chip px-3 text-[13px] font-semibold transition-colors',
    active ? 'bg-ink text-white' : 'bg-bg-soft text-muted hover:bg-primary-50',
  )
const groupLabel = 'mr-1 text-[13px] font-semibold text-muted'

function SkeletonCard() {
  return (
    <Card className="flex animate-pulse flex-col gap-3" aria-hidden="true">
      <div className="h-5 w-40 rounded-chip bg-bg-soft" />
      <div className="h-6 w-2/3 rounded-chip bg-bg-soft" />
      <div className="h-4 w-1/2 rounded-chip bg-bg-soft" />
      <div className="h-16 w-full rounded-panel bg-bg-soft" />
    </Card>
  )
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
  const [filter, setFilter] = useState<Filter>('all')
  const [sort, setSort] = useState<Sort>('recommend')
  // null = 기본 탭. 새 문장은 이 화면을 새로 열므로 null 로 시작하고, 칩 수정 때는 지금 탭을 고정한다
  const [tab, setTab] = useState<VerdictTab | null>(null)
  // null = 기본값(핵심 4항목 중 빈 게 있으면 펼침). 한 번 정해지면 칩 수정으로 재요청해도 유지한다
  const [chipsOpen, setChipsOpen] = useState<boolean | null>(null)

  // 입력(문장·칩 수정)이 바뀔 때마다 다시 요청. 늦게 도착한 이전 응답은 버린다
  useEffect(() => {
    if (!req) return
    let alive = true
    setStatus('loading')
    setError(null)
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

  // 로딩 단계 문구 (실제 서버 단계와 무관한 표시용 타이머)
  useEffect(() => {
    if (status !== 'loading') return
    setStep(0)
    const id = window.setInterval(() => setStep((s) => Math.min(s + 1, LOADING_STEPS.length - 1)), 900)
    return () => window.clearInterval(id)
  }, [status])

  const counts: Record<VerdictTab, number> | null = res && {
    eligible: res.results.filter((r) => r.verdict === '자격 충족').length,
    conditional: res.conditional.length,
    check: res.results.filter((r) => r.verdict === '확인 필요').length,
    excluded: res.excluded.length,
  }
  const active = tab ?? (counts ? defaultTab(counts) : 'eligible')

  // 필터·정렬은 선택한 탭 안에서만. 해당 안 됨 탭은 유형 정보가 없어 적용하지 않는다
  const visible = useMemo(() => {
    if (!res || active === 'excluded') return []
    const base =
      active === 'conditional'
        ? res.conditional
        : res.results.filter((r) => r.verdict === (active === 'eligible' ? '자격 충족' : '확인 필요'))
    const types = FILTERS.find((f) => f.key === filter)!.types
    const list = base.filter(
      (r) => types.length === 0 || r.program.supportTypes.some((t) => types.includes(t)),
    )
    if (sort === 'deadline')
      return [...list].sort((a, b) => (a.daysLeft ?? Infinity) - (b.daysLeft ?? Infinity))
    return list
  }, [res, active, filter, sort])

  if (!req) return <Navigate to="/support-match" replace />

  const onOverride = (key: keyof UserProfile, value: unknown) => {
    const next = { ...req, overrides: { ...req.overrides, [key]: value } }
    saveInput(next) // 새로고침해도 수정한 칩이 유지되도록
    setTab(active)
    setChipsOpen(chipsExpanded)
    setReq(next)
  }

  const CORE: (keyof UserProfile)[] = ['age', 'sido', 'bizStage', 'industryCategory']
  const chipsExpanded = chipsOpen ?? (res ? res.missing.some((k) => CORE.includes(k)) : false)

  const ageUnknownCount =
    res?.results.filter((r) => r.rules.some((x) => x.rule.kind === 'age' && x.result === 'unknown'))
      .length ?? 0

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
        {status === 'loading' && (
          <>
            <p className="text-sm text-muted">
              {LOADING_STEPS.map((s, i) => (i <= step ? s : null))
                .filter(Boolean)
                .join(' → ')}
              …
            </p>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        )}

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
            <div id="profile-chips" className="scroll-mt-6">
              <ProfileChips
                text={req.text}
                profile={res.profile}
                missing={res.missing}
                open={chipsExpanded}
                onToggle={() => setChipsOpen(!chipsExpanded)}
                onOverride={onOverride}
              />
            </div>

            {/* 모집 중 공고 자체가 0건일 때만 (요약 구간의 합 = 모집 중 공고 수) */}
            {res.results.length + res.conditional.length + res.excluded.length === 0 ? (
              <Card className="flex flex-col gap-3">
                <p className="text-[15px] font-bold text-ink">조건에 맞는 모집 중 공고가 없어요</p>
                <p className="text-sm text-muted">지역이나 창업 단계 조건을 바꿔서 다시 찾아보세요.</p>
              </Card>
            ) : (
              <>
                {/* 0건: 자격 충족·조건부가 모두 없으면 기본 탭이 확인 필요(없으면 해당 안 됨)로 열린다 */}
                {counts!.eligible + counts!.conditional === 0 && (
                  <div
                    role="status"
                    className="flex items-start gap-2 rounded-panel bg-info-soft px-4 py-3 text-sm text-ink-soft"
                  >
                    <Icon name="info" size={16} className="mt-0.5 shrink-0 text-primary-600" />
                    <span className="flex flex-col items-start gap-1">
                      <span>
                        <span className="font-semibold text-ink">조건을 수정해보세요.</span> 지금 신청 가능한 공고가 없어요.
                        위 &lsquo;이렇게 이해했어요&rsquo;의 칩을 눌러 나이·지역·창업 단계를 고치면 다시 판정해요.
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setChipsOpen(true)
                          document.getElementById('profile-chips')?.scrollIntoView({ behavior: 'smooth' })
                        }}
                        className="inline-flex min-h-10 items-center gap-1 font-semibold text-primary-600"
                      >
                        조건 수정하러 가기
                        <Icon name="arrow-right" size={14} />
                      </button>
                    </span>
                  </div>
                )}
                <VerdictTabs counts={counts!} active={active} onChange={setTab}>
                  {counts![active] === 0 ? (
                    <Card>
                      <p className="text-sm text-muted">{VERDICT_TABS.find((t) => t.key === active)!.empty}</p>
                    </Card>
                  ) : active === 'excluded' ? (
                    <ExcludedList items={res.excluded} />
                  ) : (
                    <>
                      {/* 판정별 큰 상자: 위에 유형 필터·정렬, 안에 공고 카드 격자 (모바일 1열) */}
                      <Card className="flex flex-col gap-5">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="지원 유형">
                            <span aria-hidden="true" className={groupLabel}>
                              유형
                            </span>
                            {FILTERS.map((f) => (
                              <button
                                key={f.key}
                                type="button"
                                aria-pressed={filter === f.key}
                                onClick={() => setFilter(f.key)}
                                className={tabCls(filter === f.key)}
                              >
                                {f.label}
                              </button>
                            ))}
                          </div>
                          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="정렬">
                            <span aria-hidden="true" className={groupLabel}>
                              정렬
                            </span>
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
                        </div>
                        {/* 나이 unknown 은 확인 필요 판정에서만 생긴다 */}
                        {active === 'check' && ageUnknownCount > 0 && (
                          <p className="text-[13px] text-warn">
                            나이를 알려주시면 {ageUnknownCount}건을 더 정확히 판정할 수 있어요.
                          </p>
                        )}
                        {visible.length === 0 ? (
                          <p className="text-sm text-muted">이 유형에 해당하는 공고가 없어요. 다른 유형을 확인해보세요.</p>
                        ) : (
                          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                            {visible.map((r) => (
                              <MatchCard key={r.program.id} result={r} profile={res.profile} />
                            ))}
                          </div>
                        )}
                      </Card>
                    </>
                  )}
                </VerdictTabs>
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
