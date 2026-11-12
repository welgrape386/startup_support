/* 판정에 넣지 않는 원문 조항 (명세 3-2b, 6-B). 중복 수혜 제한·예외 문구를 원문 그대로 보여주기만 한다 */

import { allRules } from './eligibility'
import type { DuplicatePolicy, ExceptionClause, SupportProgram } from './types'
import { normalizeText } from './validate'

const inField = (p: SupportProgram, section: string, quote: string) => {
  const q = normalizeText(quote)
  return !!q && normalizeText(p.fields[section] ?? '').includes(q)
}

/** quote 가 해당 항목 원문에 그대로 없으면 '미확인'으로 내린다 (추정 금지) */
export function verifiedDuplicatePolicy(p: SupportProgram): DuplicatePolicy {
  const d = p.duplicatePolicy
  return d.status === '미확인' || inField(p, d.section, d.quote) ? d : { status: '미확인' }
}

// "지원제외기준" 항목 전체, 그 밖의 항목에서는 "~별 상이", "단, ~", "~ 제외"·"예외" 가 들어간 구절
const EXCEPTION = /별\s*상이|(^|\s)단[,\s]|제외|예외/

/** 예외 조항 후보. 이미 규칙 quote 로 구조화된 구절은 뺀다 (예: 지원제외기준 → region 규칙) */
export function exceptionClauses(p: SupportProgram): ExceptionClause[] {
  const used = new Set(allRules(p).map((r) => normalizeText(r.quote)))
  const out: ExceptionClause[] = []
  for (const [section, text] of Object.entries(p.fields)) {
    const parts = section === '지원제외기준' ? [text] : text.split(/[\n()]|(?<=\.)\s/)
    for (const part of parts) {
      const quote = normalizeText(part)
      if (!quote || used.has(quote)) continue
      if (section === '지원제외기준' || EXCEPTION.test(quote)) out.push({ quote, section })
    }
  }
  return out
}
