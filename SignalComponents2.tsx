import { useCallback, useEffect, useState } from "react";
import "./signal-components2.css";

export type Verdict = "red" | "yellow" | "green" | "unknown";
const verdictMeta: Record<Verdict, string> = {
  green: "자격 충족", yellow: "조건부 가능", unknown: "확인 필요", red: "자격 미달",
};

export function SignalLight({ verdict, size = "card", animated = false }: {
  verdict: Verdict;
  size?: "tiny" | "card" | "hero" | "loader";
  animated?: boolean;
}) {
  return (
    <div role="img" aria-label={`${verdictMeta[verdict]} 신호등`}
      className={`signal signal--${size} ${animated ? "signal--animated" : ""}`}>
      {(["red", "yellow", "green"] as Verdict[]).map(color => (
        <span key={color} className={`signal__lamp signal__lamp--${color} ${color === verdict ? "is-on" : ""}`} />
      ))}
    </div>
  );
}

export function HeroSignal() {
  return (
    <div className="hero__visual">
      <div className="signal-orbit signal-orbit--one" />
      <div className="signal-orbit signal-orbit--two" />
      <SignalLight animated size="hero" verdict="green" />
      <div className="floating-note floating-note--top">
        <span className="status-dot status-dot--yellow">?</span>
        <div><small>추가 확인</small><strong>조건을 놓치지 않아요</strong></div>
      </div>
      <div className="floating-note floating-note--bottom">
        <span className="status-dot status-dot--green">✓</span>
        <div><small>판정 완료</small><strong>근거까지 한눈에</strong></div>
      </div>
    </div>
  );
}

const steps = [
  "입력하신 조건을 해석하고 있어요.",
  "지원사업 공고를 확인하고 있어요.",
  "신청 자격을 비교하고 있어요.",
];

export function Analyzing({ step }: { step: number }) {
  const safeStep = Math.min(2, Math.max(0, step));
  const verdicts: Verdict[] = ["red", "yellow", "green"];
  return (
    <main className="analyzing page-enter">
      <div className="analyzing__content signal-container">
        <div className="analyzing__signal">
          <div className="analysis-ring" />
          <SignalLight size="loader" verdict={verdicts[safeStep]} />
        </div>
        <span className="step-label">ANALYZING · {safeStep + 1}/3</span>
        <h1>{steps[safeStep]}</h1>
        <p>입력하신 내용과 공고의 자격 조건을 하나씩 비교하고 있습니다.</p>
        <div className="analysis-progress">
          {steps.map((label, index) => (
            <div className={index <= safeStep ? "is-active" : ""} key={label}>
              <span>{index < safeStep ? "✓" : index + 1}</span>
              <p>{label.replace("하고 있어요.", "")}</p>
            </div>
          ))}
        </div>
        <div className="skeletons" aria-hidden="true">
          {[1, 2, 3].map(item => (
            <div className="skeleton-card" key={item}>
              <i /><div><b /><span /><span /></div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

export function SignalSummaryBar({ counts, activeFilter, setActiveFilter }: {
  counts: Record<Verdict, number>;
  activeFilter: Verdict | "all";
  setActiveFilter: (filter: Verdict | "all") => void;
}) {
  return (
    <section className="summary-section">
      <div className="summary-copy">
        <span className="section-kicker">MATCHING RESULT</span>
        <h2>내 지원사업 신호</h2>
        <p>신호를 눌러 결과를 빠르게 모아보세요.</p>
      </div>
      <div className="summary-signal">
        {(["green", "yellow", "unknown", "red"] as Verdict[]).map(verdict => (
          <button type="button" aria-pressed={activeFilter === verdict}
            className={`${activeFilter === verdict ? "is-active" : ""} summary-lamp summary-lamp--${verdict}`}
            key={verdict}
            onClick={() => setActiveFilter(activeFilter === verdict ? "all" : verdict)}>
            <span>{counts[verdict]}</span>
            <div><strong>{verdictMeta[verdict]}</strong><small>{counts[verdict]}건</small></div>
          </button>
        ))}
      </div>
    </section>
  );
}

// 원본 App.tsx의 분석 전환 시간: 0ms, 700ms, 1400ms, 완료 2200ms.
export function useSignalAnalysis(onComplete: () => void) {
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (!running) return;
    setStep(0);
    const first = window.setTimeout(() => setStep(1), 700);
    const second = window.setTimeout(() => setStep(2), 1400);
    const done = window.setTimeout(() => { setRunning(false); onComplete(); }, 2200);
    return () => [first, second, done].forEach(window.clearTimeout);
  }, [running, onComplete]);
  const start = useCallback(() => setRunning(true), []);
  return { running, step, start };
}
