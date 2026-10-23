import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/Button'
import { Card } from '@/components/Card'
import { Icon } from '@/components/Icon'
import { Container } from '@/layout/Container'
import { PageHeader } from '@/layout/PageHeader'
import { ruleProfile } from '@/lib/parse'
import { loadInput, saveInput } from '@/lib/supportMatchInput'
import { MAX_TEXT_LENGTH, MIN_TEXT_LENGTH } from '@/services/supportMatch/config'
import { shortSido } from '@/services/supportMatch/eligibility'
import { inputError } from '@/services/supportMatch/validate'
import { Analyzing, useSignalAnalysis } from '../../SignalComponents2'

const EXAMPLES = [
  '29살이고 서울 마포구에서 디저트 카페를 준비 중인 예비창업자예요. 인테리어 자금이 3천만원 정도 모자라요.',
  '36살, 경기도에서 음식점 창업을 준비하고 있어요. 창업 교육과 멘토링을 받고 싶어요.',
  '카페 창업을 생각 중인데 어떤 지원을 받을 수 있는지 모르겠어요.',
  '31살 예비창업자예요. 인천에서 소상공인으로 분식집을 열려고 하는데 보증 지원이 필요해요.',
]

/** /support-match — 입력만 받는다. 결과는 /support-match/results */
export function SupportMatch() {
  const navigate = useNavigate()
  // "조건 다시 입력"으로 돌아오면 이전 문장이 채워져 있다
  const [text, setText] = useState(() => loadInput()?.text ?? '')
  const len = text.trim().length
  const tooShort = len > 0 && len < MIN_TEXT_LENGTH
  const canSubmit = !inputError(text) && len >= MIN_TEXT_LENGTH
  // 입력하는 동안 규칙 파서가 읽은 항목을 보여줘서 빠진 정보를 바로 알 수 있게 한다
  const p = ruleProfile(text, undefined)
  const read = [
    { label: '나이', value: p.age.value != null ? `${p.age.value}세` : null },
    { label: '지역', value: p.sido.value ? [shortSido(p.sido.value), p.sigungu.value].filter(Boolean).join(' ') : null },
    { label: '업종', value: p.industryCategory.value },
  ]

  const complete = useCallback(() => {
    const req = { text: text.trim() }
    saveInput(req)
    navigate('/support-match/results', { state: req })
  }, [text, navigate])

  const { running, step, start } = useSignalAnalysis(complete)

  const submit = () => {
    if (!canSubmit) return
    start()
  }

  if (running) return <Analyzing step={step} />

  return (
    <Container className="flex flex-col gap-6 py-page-y">
      <PageHeader
        breadcrumb={[{ label: '홈', to: '/' }, { label: '지원사업 찾기' }]}
        title="받을 수 있는 창업 지원사업을 찾아드릴게요"
        description="나이, 지역, 창업 단계, 필요한 지원을 편하게 적어주세요."
      />

      <Card className="flex flex-col gap-4">
        <div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            maxLength={MAX_TEXT_LENGTH}
            aria-label="내 상황"
            placeholder="예) 29살이고 서울 마포구에서 디저트 카페를 준비 중인 예비창업자예요. 인테리어 자금이 3천만원 정도 모자라요."
            className="w-full rounded-input border border-line bg-surface px-4 py-3 text-sm leading-relaxed text-ink-soft outline-none focus:border-primary-400"
          />
          <div className="mt-1 flex items-start justify-between gap-3">
            <p className="text-[13px] text-muted" aria-live="polite">
              {text.trim() && (
                <>
                  인식된 정보{' '}
                  {read.map((r, i) => (
                    <span key={r.label}>
                      {i > 0 && ', '}
                      {r.value ? (
                        <span className="font-semibold text-ink-soft">
                          {r.label} {r.value}
                        </span>
                      ) : (
                        <span>{r.label} 없음</span>
                      )}
                    </span>
                  ))}
                  {tooShort && <span className="text-warn"> · 나이, 지역, 업종을 함께 적어주세요</span>}
                </>
              )}
            </p>
            <p className="shrink-0 text-[13px] text-muted tnum">
              {text.length}/{MAX_TEXT_LENGTH}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex, i) => (
            <button
              key={ex}
              type="button"
              onClick={() => setText(ex)}
              className="min-h-10 rounded-chip bg-bg-soft px-3.5 text-[13px] font-semibold text-muted hover:bg-primary-50"
            >
              예시 {i + 1}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-center gap-1.5 text-[13px] text-muted">
            <Icon name="info" size={12} />
            나이·지역·창업 단계를 적으면 자격을 정확히 판정할 수 있어요
          </p>
          <Button size="lg" iconRight="arrow-right" onClick={submit} disabled={!canSubmit}>
            지원사업 찾기
          </Button>
        </div>
      </Card>
    </Container>
  )
}
