import { useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { Badge } from '@/components/Badge'
import { Button, buttonClasses } from '@/components/Button'
import { Card } from '@/components/Card'
import { Icon } from '@/components/Icon'
import { cx } from '@/lib/cx'
import { Container } from '@/layout/Container'
import { PageHeader } from '@/layout/PageHeader'
import type { MatchResult, MatchVerdict } from '@/services/supportMatch/types'
import { SignalLight, type Verdict } from '../../SignalComponents2'

const verdictSignal: Record<MatchVerdict, Verdict> = {
  '자격 충족': 'green',
  '조건부': 'yellow',
  '확인 필요': 'unknown',
  '자격 미달': 'red',
}

const verdictLabel: Record<MatchVerdict, string> = {
  '자격 충족': '자격 충족',
  '조건부': '조건부 가능',
  '확인 필요': '확인 필요',
  '자격 미달': '자격 미달',
}

const ruleColor: Record<'pass' | 'fail' | 'unknown', string> = {
  pass: '#2fa865', fail: '#e5484d', unknown: '#98a1b3',
}

function won(m: number) {
  return m >= 10000 ? `${(m / 10000).toFixed(1).replace(/\.0$/, '')}억원` : `${m.toLocaleString()}만원`
}

function fmtDate(s: string) { return s.replace(/-/g, '.') }

function DdayBadge({ daysLeft }: { daysLeft: number | null }) {
  if (daysLeft === null) {
    return <span className="inline-flex items-center rounded-chip bg-info-soft px-2.5 py-0.5 text-xs font-semibold text-primary-600">상시 모집</span>
  }
  const cls = daysLeft <= 7 ? 'bg-warn-soft text-warn' : 'bg-bg-soft text-muted'
  return <span className={cx('inline-flex items-center rounded-chip px-2.5 py-0.5 text-xs font-semibold', cls)}>D-{daysLeft}</span>
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="whitespace-nowrap font-semibold text-muted">{label}</dt>
      <dd className="text-ink" style={{ wordBreak: 'keep-all', lineHeight: '1.6' }}>{value}</dd>
    </>
  )
}

function SectionTitle({ children }: { children: string }) {
  return <h2 className="mb-4 text-[15px] font-bold text-ink">{children}</h2>
}

const fileExt = (url: string) => url.split('.').pop()?.toLowerCase() ?? ''
const isPdf = (url: string) => fileExt(url) === 'pdf'
const isImage = (url: string) => ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(fileExt(url))
const isDoc = (url: string) => ['hwp', 'hwpx', 'docx', 'doc'].includes(fileExt(url))

export function SupportMatchDetail() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const result = (location.state as { result?: MatchResult } | null)?.result

  const [checked, setChecked] = useState<Record<string, boolean>>(() => {
    try {
      const raw = localStorage.getItem(`checklist-${id}`)
      return raw ? JSON.parse(raw) : {}
    } catch { return {} }
  })

  const toggleDoc = (doc: string) => {
    setChecked((prev) => {
      const next = { ...prev, [doc]: !prev[doc] }
      try { localStorage.setItem(`checklist-${id}`, JSON.stringify(next)) } catch {}
      return next
    })
  }

  if (!result || result.program.id !== id) {
    return (
      <Container className="flex flex-col gap-6 py-page-y">
        <Card className="flex flex-col items-start gap-4">
          <p className="text-[15px] font-bold text-ink">공고를 찾을 수 없어요</p>
          <p className="text-sm text-muted">목록에서 공고를 선택해 주세요.</p>
          <Button variant="secondary" onClick={() => navigate(-1)}>← 목록으로</Button>
        </Card>
      </Container>
    )
  }

  const p = result.program
  const signal = verdictSignal[result.verdict]

  // TODO: 아래 필드들은 API 연동 시 실제 데이터로 대체
  const submissionDocs = p.submissionDocs ?? []
  const bonusPoints = p.bonusPoints ?? []
  const attachmentFiles = p.attachmentFiles ?? []
  const applyUrl = p.applyUrl
  const hasRounds = (p.rounds?.length ?? 0) > 0

  return (
    <Container className="flex flex-col gap-6 py-page-y">
      <PageHeader
        breadcrumb={[
          { label: '홈', to: '/' },
          { label: '지원사업 찾기', to: '/support-match' },
          { label: '결과', to: '/support-match/results' },
          { label: '공고 상세' },
        ]}
        title={p.title}
        right={
          <button type="button" onClick={() => navigate(-1)} className={buttonClasses('secondary', 'md')}>
            ← 목록으로
          </button>
        }
      />

      {/* 2열 레이아웃 (≥900px) */}
      <div className="grid items-start gap-6 lg:grid-cols-[1fr_320px]">
        {/* ── 왼쪽 본문 ── */}
        <div className="flex flex-col gap-6">

          {/* 4.1.1 기본 정보 */}
          <Card>
            <SectionTitle>공고 개요</SectionTitle>
            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
              <InfoRow label="소관기관" value={p.agency} />
              {p.operator && <InfoRow label="수행기관" value={p.operator} />}
              <dt className="whitespace-nowrap font-semibold text-muted">지원 유형</dt>
              <dd className="flex flex-wrap gap-1">
                {p.supportTypes.map((t) => (
                  <Badge key={t} tone="info">{t}</Badge>
                ))}
              </dd>
              <InfoRow label="판정" value={verdictLabel[result.verdict]} />
              {p.fields['신청방법'] && <InfoRow label="지원 방법" value={p.fields['신청방법']} />}
              {p.fields['지원대상'] && <InfoRow label="지원 대상" value={p.fields['지원대상']} />}
              {p.contact && <InfoRow label="문의" value={p.contact} />}
            </dl>
          </Card>

          {/* 4.1.2 지원 내용 */}
          <Card>
            <SectionTitle>지원 내용</SectionTitle>
            {p.amountMaxManwon != null && (
              <p className="mb-3 text-[28px] font-extrabold tracking-tight text-primary-600">
                1인 최대 {won(p.amountMaxManwon)}
              </p>
            )}
            {p.interestRate && (
              <p className="mb-2 text-sm text-muted">
                금리: <span className="font-semibold text-ink">{p.interestRate}</span>
              </p>
            )}
            {p.supportDetail && (
              <p className="mb-2 text-sm text-ink-soft" style={{ wordBreak: 'keep-all', lineHeight: '1.6' }}>
                {p.supportDetail}
              </p>
            )}
            {p.summary && (
              <p className="text-sm text-ink-soft" style={{ wordBreak: 'keep-all', lineHeight: '1.6' }}>
                {p.summary}
              </p>
            )}
            {p.fields['지원내용'] && (
              <blockquote
                className="mt-3 border-l-2 border-primary-400 pl-3 text-[13px] italic text-muted"
                style={{ wordBreak: 'keep-all', lineHeight: '1.6' }}
              >
                {p.fields['지원내용']}
              </blockquote>
            )}
            <p className="mt-3 text-[12px] text-muted">* 원문과 대조해 확인하세요.</p>
          </Card>

          {/* 4.1.3 접수 기간 */}
          <Card>
            <SectionTitle>접수 기간</SectionTitle>
            {p.status === '마감' ? (
              <span className="inline-flex items-center rounded-chip bg-bg-soft px-3 py-1 text-sm font-semibold text-muted">마감</span>
            ) : p.rolling ? (
              <div>
                <p className="font-semibold text-ink">상시 모집</p>
                <p className="mt-1 text-[13px] text-warn">예산 소진 시 조기 마감될 수 있어요.</p>
              </div>
            ) : hasRounds ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left">
                    <th className="pb-2 font-semibold text-muted">차수</th>
                    <th className="pb-2 font-semibold text-muted">접수 기간</th>
                    <th className="pb-2 font-semibold text-muted">상태</th>
                  </tr>
                </thead>
                <tbody>
                  {p.rounds!.map((r) => (
                    <tr key={r.round} className="border-b border-line">
                      <td className="py-2 text-ink">{r.round}</td>
                      <td className="py-2 text-ink">{fmtDate(r.start)} ~ {fmtDate(r.end)}</td>
                      <td className="py-2">
                        <span className={cx('text-xs font-semibold',
                          r.status === '접수중' ? 'text-pos' : r.status === '예정' ? 'text-primary-600' : 'text-muted')}>
                          {r.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-sm text-ink">
                  {p.applyStart ? fmtDate(p.applyStart) : '—'} ~ {p.applyEnd ? fmtDate(p.applyEnd) : '—'}
                </p>
                <DdayBadge daysLeft={result.daysLeft} />
              </div>
            )}
          </Card>

          {/* 4.1.4 자격 조건 */}
          <Card>
            <SectionTitle>자격 조건</SectionTitle>
            {result.rules.length === 0 ? (
              <p className="text-sm text-muted">정보 없음</p>
            ) : (
              <ul className="flex flex-col gap-4">
                {result.rules.map((rr, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    <span
                      className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{
                        background: ruleColor[rr.result],
                        border: rr.result === 'unknown' ? '1.5px solid #cfd6e4' : 'none',
                      }}
                      aria-hidden="true"
                    />
                    <div className="flex flex-col gap-1">
                      <span className="text-sm text-ink" style={{ wordBreak: 'keep-all', lineHeight: '1.6' }}>
                        {rr.reason}
                      </span>
                      {rr.rule.quote && (
                        <blockquote
                          className="border-l-2 border-primary-200 pl-2 text-[12px] italic text-muted"
                          style={{ wordBreak: 'keep-all', lineHeight: '1.6' }}
                        >
                          {rr.rule.quote}
                        </blockquote>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* 4.1.5 공고 URL */}
          <div className="flex flex-wrap gap-3">
            <a
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonClasses('secondary', 'md')}
            >
              공고 사이트 바로가기
              <Icon name="arrow-right" size={15} />
            </a>
            {applyUrl && (
              <a
                href={applyUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonClasses('primary', 'md')}
              >
                신청하러 가기
                <Icon name="arrow-right" size={15} />
              </a>
            )}
          </div>

          {/* 4.2 신청 준비 */}
          <Card>
            <SectionTitle>신청 준비</SectionTitle>

            {/* 4.2.1 제출 서류 */}
            <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-muted">제출 서류</h3>
            {submissionDocs.length === 0 ? (
              <p className="text-sm text-muted">
                정보 없음 {/* TODO: API 필드 submissionDocs */}
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {submissionDocs.map((doc) => (
                  <li key={doc} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id={`doc-${doc}`}
                      checked={!!checked[doc]}
                      onChange={() => toggleDoc(doc)}
                      className="h-4 w-4 accent-primary-600"
                    />
                    <label
                      htmlFor={`doc-${doc}`}
                      className="cursor-pointer text-sm text-ink"
                      style={{ wordBreak: 'keep-all', lineHeight: '1.6' }}
                    >
                      {doc}
                    </label>
                  </li>
                ))}
              </ul>
            )}

            {/* 4.2.2 우대·가산점 */}
            <h3 className="mb-2 mt-5 text-[13px] font-semibold uppercase tracking-wide text-muted">우대·가산점</h3>
            {bonusPoints.length === 0 ? (
              <p className="text-sm text-muted">
                우대·가산점 정보가 없어요. {/* TODO: API 필드 bonusPoints */}
              </p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {bonusPoints.map((b) => (
                  <li key={b}><Badge tone="info">{b}</Badge></li>
                ))}
              </ul>
            )}
          </Card>

          {/* 4.3 원문 파일 */}
          {attachmentFiles.length > 0 && (
            <Card>
              <SectionTitle>공고 원문 파일</SectionTitle>
              <div className="flex flex-col gap-5">
                {attachmentFiles.map((file) => (
                  <div key={file.url} className="flex flex-col gap-2">
                    <p className="text-sm font-semibold text-ink">{file.name}</p>
                    {isPdf(file.url) ? (
                      <>
                        <iframe
                          src={file.url}
                          title={file.name}
                          className="w-full rounded-panel border border-line"
                          style={{ height: 640 }}
                        />
                        <div className="flex gap-4 text-sm">
                          <a href={file.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-primary-600">새 탭에서 열기</a>
                          <a href={file.url} download className="font-semibold text-muted">다운로드</a>
                        </div>
                      </>
                    ) : isImage(file.url) ? (
                      <>
                        <img src={file.url} alt={file.name} className="max-h-48 w-auto rounded-panel border border-line object-contain" />
                        <a href={file.url} download className={buttonClasses('secondary', 'md')}>다운로드</a>
                      </>
                    ) : isDoc(file.url) ? (
                      <a href={file.url} download className={buttonClasses('secondary', 'md')}>
                        다운로드 ({fileExt(file.url).toUpperCase()})
                      </a>
                    ) : (
                      <a href={file.url} target="_blank" rel="noopener noreferrer" className={buttonClasses('secondary', 'md')}>열기</a>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* ── 오른쪽 sticky 요약 카드 ── */}
        <div className="lg:sticky lg:top-6">
          <Card className="flex flex-col gap-4">
            <div className="flex items-start gap-3">
              <div className="shrink-0 pt-0.5">
                <SignalLight size="card" verdict={signal} />
              </div>
              <div>
                <p className="text-xs font-semibold text-primary-600">{verdictLabel[result.verdict]}</p>
                <p className="mt-0.5 text-sm font-bold text-ink" style={{ wordBreak: 'keep-all', lineHeight: '1.5' }}>
                  {p.title}
                </p>
              </div>
            </div>
            {p.amountMaxManwon != null && (
              <p className="text-[20px] font-extrabold tracking-tight text-primary-600">
                최대 {won(p.amountMaxManwon)}
              </p>
            )}
            <div className="flex flex-col gap-1 text-sm text-muted">
              {p.rolling ? (
                <span>상시 모집</span>
              ) : p.applyEnd ? (
                <span className="flex items-center gap-2">
                  마감 {fmtDate(p.applyEnd)}
                  <DdayBadge daysLeft={result.daysLeft} />
                </span>
              ) : null}
              <span>{p.agency}{p.operator ? ` · ${p.operator}` : ''}</span>
            </div>
            <div className="flex flex-col gap-[10px]">
              <a
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonClasses('primary', 'md', 'w-full')}
              >
                공고 원문 보기
                <Icon name="arrow-right" size={15} />
              </a>
              {applyUrl && (
                <a
                  href={applyUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={buttonClasses('primary', 'md', 'w-full')}
                >
                  신청하러 가기
                  <Icon name="arrow-right" size={15} />
                </a>
              )}
              <a
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex w-full items-center justify-center rounded-btn h-10 px-4 text-sm gap-1.5 font-semibold transition-colors bg-white text-primary-600 border border-primary-500 hover:bg-[#f2f6ff]"
              >
                공고 사이트 바로가기
                <Icon name="arrow-right" size={15} />
              </a>
            </div>
          </Card>
        </div>
      </div>
    </Container>
  )
}
