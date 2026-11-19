import { useCallback, useEffect, useRef, useState } from 'react'
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
  '만 29세이고 서울 마포구에서 디저트 카페를 준비 중인 예비창업자예요. 인테리어 자금이 3천만원 정도 모자라요.',
  '36살, 경기도에서 음식점 창업을 준비하고 있어요. 창업 교육과 멘토링을 받고 싶어요.',
  '31살 예비창업자예요. 인천에서 소상공인으로 분식집을 열려고 하는데 보증 지원이 필요해요.',
  '만 28세, 성수동에서 베이글 가게 열려고 준비 중이에요. 인테리어 자금이 필요해요.',
]

// 나애님 user-extract API 반환 타입
interface ExtractResult {
  age: number | null
  stage: string | null
  res_sido: string | null
  res_sigungu: string | null
  res_raw: string | null
  res_candidates: string[] | null
  plan_sido: string | null
  plan_sigungu: string | null
  plan_raw: string | null
  plan_candidates: string[] | null
  biz_sido: string | null
  biz_sigungu: string | null
  biz_raw: string | null
  biz_candidates: string[] | null
  biz_months: number | null
  industry_cat: string[] | null
  industry_raw: string | null
  need: string[] | null
  ask_fields: string[] | null
}

interface ExtractResponse {
  mode: string
  ask_fields: string[] | null
  ask_text: Record<string, string>
  result: ExtractResult
}

const ASK_LABEL: Record<string, string> = {
  만나이: '나이 (만 나이, 예: 만 27세)',
  거주지: '거주지 구 (서울 기준, 예: 마포구)',
  창업예정지: '창업 예정 구 (예: 성동구)',
  사업장소재지: '사업장 소재지 구 (예: 성동구)',
  업력_개월: '창업 후 개월 수 (예: 창업 18개월째)',
  업종: '업종 (예: 디저트 카페)',
  need: '필요한 지원 (예: 자금, 교육, 공간, 홍보)',
}

/** /support-match — 입력만 받는다. 결과는 /support-match/results */
export function SupportMatch() {
  const navigate = useNavigate()
  const [text, setText] = useState(() => loadInput()?.text ?? '')
  const [extracted, setExtracted] = useState<ExtractResponse | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const len = text.trim().length
  const tooShort = len > 0 && len < MIN_TEXT_LENGTH
  const canSubmit = !inputError(text) && len >= MIN_TEXT_LENGTH

  // 입력 중 debounce 추출 (350ms, 규칙만 — API 호출 없음)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (text.trim().length < MIN_TEXT_LENGTH) {
      setExtracted(null)
      return
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const apiBase = (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ?? ''
        const res = await fetch(`${apiBase}/api/v1/user-extract`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text.trim(), mode: 'rules' }),
        })
        if (res.ok) setExtracted(await res.json())
      } catch {
        // 백엔드 미연결 시 ruleProfile fallback 사용
      }
    }, 350)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [text])

  // extracted가 없을 때 프론트 규칙 fallback
  const p = ruleProfile(text, undefined)

  // 인식된 정보 (extracted 우선, fallback은 ruleProfile)
  const r = extracted?.result ?? null

  const readAge = r ? r.age : p.age.value
  const readStage = r ? r.stage : p.bizStage.value

  // 거주지: res
  const readResSido = r?.res_sido ?? null
  const readResGu = r?.res_sigungu ?? null
  // 창업예정지: plan (예비창업일 때)
  const readPlanSido = r?.plan_sido ?? null
  const readPlanGu = r?.plan_sigungu ?? null
  // 사업장: biz (초기창업일 때)
  const readBizSido = r?.biz_sido ?? null
  const readBizGu = r?.biz_sigungu ?? null
  // fallback용 단일 지역
  const readSido = readPlanSido ?? readBizSido ?? readResSido ?? (extracted ? null : p.sido.value)
  const readGu = readPlanGu ?? readBizGu ?? readResGu ?? (extracted ? null : p.sigungu.value)

  const readIndustry = r
    ? (r.industry_raw ? `${r.industry_cat?.[0] ?? ''} (${r.industry_raw})`.trim() : (r.industry_cat?.[0] ?? null))
    : p.industryCategory.value
  const readNeed = r?.need ?? null
  const readBizMonths = r?.biz_months ?? null

  // 인식된 정보 chip 목록 (나애님 명세 기준)
  const read = [
    { label: '나이', value: readAge != null ? `만 ${readAge}세` : null },
    // 거주지 (res_sigungu 있을 때만, 없으면 단일 지역으로 fallback)
    ...(readResGu
      ? [{ label: '거주', value: `${readResGu}` }]
      : !readPlanGu && !readBizGu && readSido
        ? [{ label: '지역', value: [shortSido(readSido as string), readGu].filter(Boolean).join(' ') }]
        : []),
    // 창업예정지 (예비창업)
    ...(readPlanGu ? [{ label: '창업 예정', value: readPlanGu }] : []),
    // 사업장 (초기창업)
    ...(readBizGu ? [{ label: '사업장', value: readBizGu }] : []),
    { label: '단계', value: readStage },
    // 업력 (초기창업일 때)
    ...(readBizMonths != null ? [{ label: '창업', value: `${readBizMonths}개월` }] : []),
    // 업종
    { label: '업종', value: readIndustry },
    // 필요 지원
    ...(readNeed && readNeed.length > 0 ? [{ label: '지원', value: readNeed.join('·') }] : []),
  ]

  // 빠진 정보: extracted.ask_fields 우선, fallback은 하드코딩 4개
  const missing: string[] = extracted?.ask_fields
    ? extracted.ask_fields.map((f) => extracted.ask_text[f] ?? ASK_LABEL[f] ?? f)
    : [
        !p.age.value && '나이(만 나이, 예: 만 27세)',
        !p.sigungu.value && '거주지 구(서울 기준, 예: 마포구)',
        !p.bizStage.value && '창업 단계(예비창업 / 초기창업)',
        !p.industryCategory.value && '업종(예: 카페, 음식점)',
      ].filter((x): x is string => Boolean(x))

  // 겹치는 동 안내: res/plan/biz candidates 모두 체크
  const ambiguousList: { raw: string; candidates: string[] }[] = []
  if (r?.res_candidates && r.res_candidates.length > 1)
    ambiguousList.push({ raw: r.res_raw ?? '거주지', candidates: r.res_candidates })
  if (r?.plan_candidates && r.plan_candidates.length > 1)
    ambiguousList.push({ raw: r.plan_raw ?? '창업예정지', candidates: r.plan_candidates })
  if (r?.biz_candidates && r.biz_candidates.length > 1)
    ambiguousList.push({ raw: r.biz_raw ?? '사업장', candidates: r.biz_candidates })

  // 서울 밖 창업 안내: 창업예정지 또는 사업장의 sido가 서울 외 지역일 때
  const isOutsideSeoul =
    (r?.plan_sido != null && r.plan_sido !== '서울특별시') ||
    (r?.biz_sido != null && r.biz_sido !== '서울특별시')

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

      {/* 입력 가이드: 항목별 격자 + 태그로 구분한다. 배경·테두리는 메인 "이렇게 적으면 정확해져요"와 같은 값 */}
      <Card className="flex flex-col gap-5" style={{ background: '#f2f6ff', border: '1px solid #dbe5ff' }}>
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-info-soft text-primary-600">
            <Icon name="info" size={18} />
          </span>
          <h2 className="text-[17px] font-bold text-ink">이렇게 적어 주세요</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="flex flex-col gap-2 rounded-panel border border-primary-100 bg-surface p-4">
            <span className="w-fit rounded-chip bg-primary-600 px-2.5 py-0.5 text-xs font-bold text-white">필수</span>
            <ul className="text-[13px] leading-relaxed text-ink space-y-0.5">
              <li>· 나이 <span className="text-muted">(만 나이)</span></li>
              <li>· 지역 <span className="text-muted">(거주지 구 + 사업장/창업예정 구)</span></li>
              <li>· 창업 단계 <span className="text-muted">(초기창업자/예비창업자 + 개월 수)</span></li>
              <li>· 업종</li>
            </ul>
          </div>
          <div className="flex flex-col gap-2 rounded-panel border border-primary-100 bg-surface p-4">
            <span className="w-fit rounded-chip bg-info-soft px-2.5 py-0.5 text-xs font-bold text-primary-700">기존 창업자</span>
            <ul className="text-[13px] leading-relaxed text-ink space-y-0.5">
              <li>· 거주지 구</li>
              <li>· 사업장 소재지 구</li>
              <li>· 창업 후 개월 수 <span className="text-muted">(예: 창업 18개월째)</span></li>
            </ul>
          </div>
          <div className="flex flex-col gap-2 rounded-panel border border-primary-100 bg-surface p-4">
            <span className="w-fit rounded-chip bg-info-soft px-2.5 py-0.5 text-xs font-bold text-primary-700">예비 창업자</span>
            <ul className="text-[13px] leading-relaxed text-ink space-y-0.5">
              <li>· 거주지 구</li>
              <li>· 창업 예정 구</li>
              <li className="text-muted text-[12px]">※ 아직 사업자 등록 전이면 개월 수 불필요</li>
            </ul>
          </div>
        </div>
        <div className="flex flex-col gap-1.5 rounded-panel border border-primary-100 bg-surface px-4 py-3">
          <span className="text-[12px] font-bold text-muted">추가하면 좋은 것들</span>
          <p className="text-[13px] leading-relaxed text-ink">
            필요한 지원 종류 <span className="text-muted">(자금·교육·공간·홍보·인력 등)</span>, 신청자 유형 <span className="text-muted">(개인/법인)</span>, 성별 — 해당 조건이 있는 공고에서 더 정확한 판정이 가능해요.
          </p>
        </div>
        <div className="flex flex-col gap-1.5 rounded-panel border border-primary-100 bg-surface px-4 py-3">
          <span className="text-[12px] font-bold text-muted">예시</span>
          <p className="text-[13px] leading-relaxed text-ink">예) 만 29세이고 서울 마포구에 살고 있어요. 성수동에서 디저트 카페 창업을 준비 중인 예비창업자예요.</p>
        </div>
      </Card>

      <Card className="flex flex-col gap-4">
        <div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            maxLength={MAX_TEXT_LENGTH}
            aria-label="내 상황"
            placeholder="예) 만 29세이고 서울 마포구에서 디저트 카페를 준비 중인 예비창업자예요. 인테리어 자금이 3천만원 정도 모자라요."
            className="w-full rounded-input border border-line bg-surface px-4 py-3 text-sm leading-relaxed text-ink-soft outline-none focus:border-primary-400"
          />
          <div className="mt-1 flex items-start justify-between gap-3">
            <div className="flex flex-col gap-0.5 text-[13px] text-muted" aria-live="polite">
              {text.trim() && (
                <>
                  {/* 1줄: 인식된 정보 */}
                  <p>
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
                  </p>
                  {/* 2줄: 추가하면 더 정확해요 (tooShort 포함) */}
                  {tooShort && (
                    <p className="text-warn">나이, 지역, 업종을 함께 적어주세요</p>
                  )}
                  {!tooShort && missing.length > 0 && (
                    <p className="text-warn">추가하면 더 정확해요: {missing.join(', ')}</p>
                  )}
                  {/* 3줄+: 겹치는 동 안내, 서울 밖 안내 */}
                  {ambiguousList.map(({ raw, candidates }) => (
                    <p key={raw} className="text-warn">
                      · {raw}은(는) {candidates.join(' · ')}에 있어요 — 구 이름으로 적어주세요
                    </p>
                  ))}
                  {isOutsideSeoul && (
                    <p className="text-warn">
                      · 이 서비스는 서울에서 창업하는 분 대상이에요. 서울 외 지역은 일부 공고가 맞지 않을 수 있어요.
                    </p>
                  )}
                </>
              )}
            </div>
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

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
          <Button size="lg" iconRight="arrow-right" onClick={submit} disabled={!canSubmit}>
            지원사업 찾기
          </Button>
        </div>
      </Card>
    </Container>
  )
}
