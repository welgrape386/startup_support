import { useCallback, useState } from "react";
import { Analyzing, HeroSignal, SignalSummaryBar, useSignalAnalysis, type Verdict } from "./SignalComponents";

export default function ExampleApp() {
  const [screen, setScreen] = useState<"home" | "results">("home");
  const [filter, setFilter] = useState<Verdict | "all">("all");
  const complete = useCallback(() => setScreen("results"), []);
  const { running, step, start } = useSignalAnalysis(complete);
  if (running) return <Analyzing step={step} />;
  if (screen === "home") return (
    <main style={{minHeight:"100vh", background:"#f8fafd", padding:"60px 20px", textAlign:"center"}}>
      <HeroSignal />
      <h1>받을 수 있는 창업 지원사업을 찾아드릴게요</h1>
      <button onClick={start} style={{marginTop:24,padding:"15px 24px",background:"#4169e1",color:"white",border:0,borderRadius:12,cursor:"pointer"}}>
        지원사업 신호 확인하기 →
      </button>
    </main>
  );
  return <main style={{maxWidth:1100,margin:"50px auto",padding:"0 20px"}}>
    <SignalSummaryBar counts={{red:2,yellow:3,green:4}} activeFilter={filter} setActiveFilter={setFilter}/>
    <p style={{marginTop:24}}>현재 필터: {filter === "all" ? "전체" : filter} (여기에 기존 결과 목록 연결)</p>
    <button onClick={() => setScreen("home")}>처음으로</button>
  </main>;
}
