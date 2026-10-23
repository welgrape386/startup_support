# 지원신호등 UI/모션 추출본

원본 Figma Make 코드에서 선택한 UI를 독립 컴포넌트로 분리했습니다.

## 파일
- `SignalComponents.tsx`: SignalLight, HeroSignal, Analyzing, SignalSummaryBar, useSignalAnalysis
- `signal-components.css`: 원본 신호등 색상/크기/발광/궤도/분석 모션/결과 요약 UI 스타일 + 모바일 대응
- `ExampleApp.tsx`: 버튼 → 분석(0/700/1400ms) → 결과(2200ms) 작동 예시

## Figma Make에 적용
1. `SignalComponents.tsx`와 `signal-components.css`를 같은 폴더(예: src/components)에 넣습니다.
2. 원하는 화면에서 `HeroSignal`, `Analyzing`, `SignalSummaryBar`를 import합니다.
3. 전체 연결을 확인하려면 `ExampleApp.tsx`를 `src/App.tsx`로 사용하고 import 경로를 실제 폴더에 맞게 수정합니다.
4. 실제 데이터로 바꾸려면 `counts={{red:2,yellow:3,green:4}}`를 계산된 건수로 교체하고, 필터 상태를 결과 목록에 연결합니다.

원본 디자인의 CSS 기반 신호등이며 PNG 이미지가 아닙니다. React + TypeScript 환경용입니다.
