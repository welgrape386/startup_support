/**
 * 사용자 업종 카테고리 9개 (나애·예은님 정리, 시스템 정리 문서 "우리 업종 카테고리").
 * 원하는 지원 카테고리(자금·교육 등)와 별개다. 판정 매칭 표는 아직 연결 전이다.
 */
export const INDUSTRY_CATEGORIES = [
  '음식·카페',
  '식품 제조·농식품',
  '도소매·판매',
  '생활 서비스',
  '공방·제조',
  'IT·소프트웨어',
  '디자인·콘텐츠',
  '첨단기술',
  '기타',
] as const

export type IndustryCategory = (typeof INDUSTRY_CATEGORIES)[number]
