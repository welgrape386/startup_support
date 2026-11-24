/** 실데이터 기반 조건 체크리스트
 * conditionTexts({label, text}) → 🟡/⚪ 조건 목록 표시
 * signal 전체 결과도 받아서 🟢/🔴 항목도 표시
 */

type CondItem = string | { label: string; text: string }

interface Props {
  signal: string
  conditionTexts?: CondItem[]
  results?: Record<string, string>  // 백엔드 판정 결과 {조건명: "✅"|"🟡"|"❔"|"❌"}
}

const SIGNAL_MARK: Record<string, { sym: string; text: string; cls: string }> = {
  '✅': { sym: '✔', text: '충족',      cls: 'text-pos' },
  '🟡': { sym: '!', text: '조건부',    cls: 'text-warn' },
  '❔': { sym: '?', text: '확인 필요', cls: 'text-muted' },
  '❌': { sym: '✘', text: '미충족',    cls: 'text-neg' },
}

const LABEL_KO: Record<string, string> = {
  '나이': '나이',
  '지역': '소재지',
  '사업자등록': '사업자등록',
  '업력': '업력',
  '업종': '업종',
  '신청자_유형': '신청자 유형',
  '성별': '성별',
  '특수자격': '대상 자격',
  '대안조건': '대안조건',
}

export function ConditionChecklist({ signal, conditionTexts, results }: Props) {
  // results가 있으면 전체 조건 표시, 없으면 conditionTexts만 표시
  const rows: { label: string; text: string; mark: string }[] = []

  if (results && Object.keys(results).length > 0) {
    for (const [name, mark] of Object.entries(results)) {
      // conditionTexts에서 같은 레이블의 text 찾기
      const matched = (conditionTexts || []).find(item =>
        typeof item === 'object' && item.label === LABEL_KO[name]
      )
      const text = typeof matched === 'object' ? matched.text : ''
      rows.push({ label: LABEL_KO[name] || name, text, mark })
    }
  } else if (conditionTexts && conditionTexts.length > 0) {
    for (const item of conditionTexts) {
      const label = typeof item === 'object' ? item.label : '조건'
      const text = typeof item === 'object' ? item.text : item
      rows.push({ label, text, mark: '🟡' })
    }
  }

  if (rows.length === 0) {
    return (
      <ul className="flex flex-col divide-y divide-line rounded-panel border border-line bg-surface">
        <li className="px-2.5 py-2 text-[13px] text-muted">조건 정보 없음</li>
      </ul>
    )
  }

  return (
    <ul className="flex max-h-64 flex-col divide-y divide-line overflow-y-auto rounded-panel border border-line bg-surface">
      {rows.map((row, i) => {
        const m = SIGNAL_MARK[row.mark] ?? { sym: '?', text: '확인 필요', cls: 'text-muted' }
        return (
          <li key={i} className="flex items-start justify-between gap-3 px-2.5 py-2 text-[13px]">
            <span className="min-w-0 text-ink-soft">
              <span className="font-semibold text-ink">{row.label}</span>
              {row.text && <span className="ml-1">{row.text}</span>}
            </span>
            <span className={`shrink-0 font-bold whitespace-nowrap ${m.cls}`}>
              <span aria-hidden="true">{m.sym}</span> {m.text}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
