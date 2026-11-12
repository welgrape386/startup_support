import { Icon } from '@/components/Icon'
import { TOP_CARD, TOP_CARD_TITLE } from './topCard'

/** 진단 결과 전체를 묶은 AI 3줄 요약. 공고 카드의 사업 요약(program.summary)과 다른, 결과 화면 맨 위 카드.
    판정색이 많은 화면이라 흰 카드 + 회색 테두리로 두고, 색은 AI 아이콘에만 쓴다.
    샘플 여부(source)는 데이터에만 두고 화면에는 표시하지 않는다 (원칙 4 임시 예외, CLAUDE.md) */
export function ResultSummary({ lines }: { lines: string[] }) {
  if (lines.length === 0) return null
  return (
    <section aria-labelledby="result-summary-title" className={TOP_CARD}>
      <h2 id="result-summary-title" className={TOP_CARD_TITLE}>
        <Icon name="sparkle" size={16} className="text-primary-600" />
        AI 요약
      </h2>
      <ol className="mt-3 flex flex-col gap-1.5">
        {lines.map((l, i) => (
          <li key={l} className="flex items-start gap-2.5 text-[15px] leading-[1.7] text-ink-soft">
            <span
              aria-hidden="true"
              className="mt-[3px] grid h-5 w-5 shrink-0 place-items-center rounded-full bg-bg-soft text-[11px] font-semibold text-muted"
            >
              {i + 1}
            </span>
            {l}
          </li>
        ))}
      </ol>
    </section>
  )
}
