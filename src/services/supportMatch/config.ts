/* 매칭 조정값 (명세 4-2, 5장). 가중치는 여기 한 곳에서만 바꾼다 */

export const MAX_TEXT_LENGTH = 1000
/** 입력 화면 전용 최소 길이. 서버 계약(validate.inputError)은 1자부터 받는다 */
export const MIN_TEXT_LENGTH = 10

export const SCORE = {
  similarity: 45,
  passRate: 35,
  needs: 20,
  unknownPenalty: 5,
  unknownPenaltyMax: 15,
  /** 후보가 이보다 적으면 유사도 min-max 정규화를 하지 않는다 */
  normalizeMinCandidates: 3,
}

/** 한 걸음만 더: 공고 수가 많은 (항목, 값) 묶음 상위 N개만 보여준다 (명세 6-C) */
export const NEXT_STEPS_MAX = 3
