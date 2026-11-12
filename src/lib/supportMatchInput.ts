import type { SupportMatchRequest } from '@/services/supportMatch/types'

/* 입력 화면 → 결과 화면으로 넘기는 입력. 주소창에 넣지 않고 sessionStorage 에 둔다
   (새로고침해도 유지, 탭을 닫으면 사라짐). 저장이 막힌 브라우저(사생활 보호 모드 등)에서는
   라우터 state 로 넘긴 값만 쓴다. */

const KEY = 'supportMatch:input'

export function loadInput(): SupportMatchRequest | null {
  try {
    const v = JSON.parse(sessionStorage.getItem(KEY) ?? 'null')
    return typeof v?.text === 'string' ? v : null
  } catch {
    return null
  }
}

export function saveInput(req: SupportMatchRequest) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(req))
  } catch {
    /* 저장할 수 없으면 라우터 state 로만 전달된다 */
  }
}
