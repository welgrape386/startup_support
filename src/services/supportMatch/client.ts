import type { SupportMatchError, SupportMatchRequest, SupportMatchResponse } from './types'
import { verifiedSummaryLines } from './summary'
import { mockSummaryLines } from './uiPlaceholder'
import { inputError } from './validate'

export class SupportMatchApiError extends Error {
  code: string
  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

/** 화면이 바로 쓰는 필드가 다 있는가. 없으면 렌더링 중 깨지므로 오류 카드로 보낸다 */
function isMatchResponse(b: unknown): b is SupportMatchResponse {
  const r = b as Partial<SupportMatchResponse> | null
  return (
    !!r &&
    typeof r === 'object' &&
    !!r.profile &&
    !!r.meta &&
    !!r.summary &&
    Array.isArray(r.missing) &&
    Array.isArray(r.results) &&
    Array.isArray(r.conditional) &&
    Array.isArray(r.excluded) &&
    Array.isArray(r.nextSteps)
  )
}

const NOT_JSON = Symbol('not-json')

/**
 * POST /api/support-match.
 * 연결 실패, JSON 이 아닌 응답, 오류 응답은 SupportMatchApiError 로 던진다. 샘플 데이터로 대체하지 않는다.
 * 백엔드가 아직 판정 AI 가 없을 때는 meta.dataSource='mock' 으로 응답하고, 화면에 "샘플 데이터" 띠가 뜬다.
 */
export async function fetchSupportMatch(req: SupportMatchRequest): Promise<SupportMatchResponse> {
  const invalid = inputError(req.text)
  if (invalid) throw new SupportMatchApiError('INVALID_INPUT', invalid)
  const text = req.text.trim()

  let res: Response
  try {
    res = await fetch('/api/support-match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...req, text }),
    })
  } catch {
    throw new SupportMatchApiError('INTERNAL', '서버에 연결하지 못했어요.')
  }

  const body: unknown = await res.json().catch(() => NOT_JSON)
  if (body === NOT_JSON) throw new SupportMatchApiError('INTERNAL', '서버 응답을 읽지 못했어요. 잠시 후 다시 시도해주세요.')
  if (!res.ok) {
    const e = (body as SupportMatchError | null)?.error
    throw new SupportMatchApiError(e?.code ?? 'INTERNAL', e?.message ?? '잠시 후 다시 시도해주세요.')
  }
  if (!isMatchResponse(body)) throw new SupportMatchApiError('INTERNAL', '결과를 읽지 못했어요. 잠시 후 다시 시도해주세요.')
  return body
}

/**
 * 진단 결과 전체에 대한 AI 3줄 요약 (공고별 요약 아님).
 * API 가 생기기 전까지는 판정 결과로 만든 샘플 문장을 돌려준다(source='mock' → 화면에 "샘플" 표시).
 * API 연결 시 lines 를 가져오는 부분만 바꾸고, 숫자 검증(verifiedSummaryLines)은 그대로 둔다.
 */
export async function fetchResultSummary(res: SupportMatchResponse): Promise<{ lines: string[]; source: 'ai' | 'mock' }> {
  return { lines: verifiedSummaryLines(mockSummaryLines(res), res), source: 'mock' }
}
