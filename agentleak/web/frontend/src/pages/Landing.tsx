import { Link } from "react-router-dom"

const channels = ["tool_call", "shared_memory", "agent_message", "log", "generated_file", "final_output"]

function Wordmark() {
  return <Link to="/" className="font-mono text-sm font-semibold tracking-[-0.04em]" aria-label="AgentLeak home">AgentLeak/</Link>
}

function TraceDemo() {
  return (
    <div className="trace-window" aria-label="Example AgentLeak audit result">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-white/45"><span>run_2048.trace</span><span>local audit</span></div>
      <div className="grid min-h-[360px] md:grid-cols-[1fr_150px]">
        <div className="space-y-1 p-4 font-mono text-[11px] leading-6 sm:p-6">
          <p className="text-white/35">01&nbsp; user_input &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; source</p>
          <p className="text-white/35">02&nbsp; tool_response &nbsp;&nbsp;&nbsp;&nbsp; source</p>
          <p className="trace-line trace-line-one text-white/80">03&nbsp; tool_call &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span className="rounded bg-white px-1.5 py-0.5 text-black">L4 secret</span></p>
          <p className="trace-line trace-line-two text-white/80">04&nbsp; shared_memory &nbsp;&nbsp;&nbsp; <span className="border-b border-white/70">L3 address</span></p>
          <p className="text-white/35">05&nbsp; agent_message &nbsp;&nbsp;&nbsp; clean</p>
          <p className="trace-line trace-line-three text-white/80">06&nbsp; log &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span className="border-b border-white/70">L2 email</span></p>
          <p className="text-white/35">07&nbsp; final_output &nbsp;&nbsp;&nbsp;&nbsp; clean</p>
          <div className="mt-8 border-t border-dashed border-white/15 pt-4 text-white/45"><p>policy &nbsp;&nbsp;&nbsp; risk_index &lt; 0.20</p><p>result &nbsp;&nbsp;&nbsp; blocked at 0.38</p></div>
        </div>
        <div className="flex flex-row border-t border-white/10 md:flex-col md:border-l md:border-t-0">
          <div className="flex flex-1 flex-col justify-between p-4"><span className="font-mono text-[9px] uppercase tracking-widest text-white/35">risk index</span><strong className="font-mono text-4xl font-medium tracking-[-0.08em] text-white">.38</strong></div>
          <div className="flex flex-1 flex-col justify-between border-l border-white/10 p-4 md:border-l-0 md:border-t"><span className="font-mono text-[9px] uppercase tracking-widest text-white/35">output</span><strong className="font-mono text-sm font-medium uppercase text-white">clean</strong></div>
        </div>
      </div>
    </div>
  )
}

export function Landing() {
  return (
    <div className="landing min-h-screen bg-[#f2f2ef] text-[#101010]">
      <header className="sticky top-0 z-50 border-b border-black/10 bg-[#f2f2ef]/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-5 sm:px-8">
          <Wordmark />
          <nav className="hidden items-center gap-7 text-xs text-black/60 md:flex" aria-label="Main navigation"><a href="#problem" className="transition-colors hover:text-black">Problem</a><a href="#method" className="transition-colors hover:text-black">Method</a><a href="#scenarios" className="transition-colors hover:text-black">Scenarios</a><a href="#evidence" className="transition-colors hover:text-black">Evidence</a></nav>
          <div className="flex items-center gap-2"><Link to="/login" className="px-3 py-2 text-xs font-medium">Sign in</Link><Link to="/register" className="bg-black px-4 py-2.5 text-xs font-medium text-white transition-transform hover:-translate-y-0.5">Create local account</Link></div>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden border-b border-black/10">
          <div className="hero-orbit" aria-hidden="true" />
          <div className="mx-auto grid max-w-[1440px] gap-14 px-5 pb-20 pt-20 sm:px-8 lg:grid-cols-[1.02fr_.98fr] lg:pb-28 lg:pt-28">
            <div className="relative z-10 flex flex-col justify-between">
              <div><p className="mb-7 font-mono text-[10px] uppercase tracking-[0.18em] text-black/50">Privacy tests for agent systems / OSS</p><h1 className="max-w-4xl text-[clamp(3.7rem,7.6vw,8.2rem)] font-medium leading-[0.82] tracking-[-0.085em]">Your output is clean.<span className="block text-black/35">Your agent may not be.</span></h1><p className="mt-9 max-w-xl text-base leading-7 text-black/62 sm:text-lg">AgentLeak tests what happens behind the answer: tool arguments, shared memory, inter-agent messages, logs and generated files. Run it locally before sensitive data reaches production.</p></div>
              <div className="mt-10 flex flex-wrap items-center gap-3"><Link to="/register" className="bg-black px-5 py-3 text-sm font-medium text-white transition-transform hover:-translate-y-0.5">Run a local audit</Link><a href="#method" className="border border-black/20 px-5 py-3 text-sm font-medium transition-colors hover:border-black">See how it works</a><span className="w-full font-mono text-[10px] text-black/42 sm:w-auto">No telemetry. No cloud required.</span></div>
            </div>
            <div className="relative z-10 lg:pt-4"><TraceDemo /></div>
          </div>
          <div className="border-t border-black/10 py-3 font-mono text-[9px] uppercase tracking-[0.18em] text-black/40"><div className="channel-marquee flex min-w-max gap-10 px-5">{[...channels, ...channels].map((channel, index) => <span key={`${channel}-${index}`}>{channel}</span>)}</div></div>
        </section>

        <section id="problem" className="mx-auto max-w-[1440px] border-x border-black/10"><div className="grid border-b border-black/10 lg:grid-cols-[.7fr_1.3fr]"><div className="p-6 sm:p-10"><p className="section-index">01 / the blind spot</p></div><div className="border-t border-black/10 p-6 sm:p-10 lg:border-l lg:border-t-0"><h2 className="max-w-4xl text-4xl font-medium leading-[1.02] tracking-[-0.055em] sm:text-6xl">The final answer is only one exit. Agent systems have many more.</h2><div className="mt-14 grid gap-8 text-sm leading-6 text-black/60 sm:grid-cols-2"><p>Traditional output checks can miss a customer record copied into a tool call, a credential written to a log, or health data passed from one agent to another.</p><p>AgentLeak treats every execution channel as part of the privacy boundary, then shows where a secret entered, who handled it and where it escaped.</p></div></div></div></section>

        <section id="method" className="bg-[#101010] text-white"><div className="mx-auto max-w-[1440px] px-5 py-24 sm:px-8 sm:py-32"><p className="section-index !text-white/40">02 / one trace in, one decision out</p><div className="mt-14 grid gap-px border border-white/15 bg-white/15 lg:grid-cols-4">{[["01", "Capture", "Record eight normalized channels from one agent or a multi-agent run."], ["02", "Detect", "Find PII, credentials and domain-sensitive data with deterministic rules."], ["03", "Trace", "Reconstruct the path from source to disclosure without storing raw values."], ["04", "Gate", "Return a normalized Risk Index and fail the build when policy is breached."]].map(([n, title, body]) => <article key={n} className="min-h-64 bg-[#101010] p-6 sm:p-8"><span className="font-mono text-[10px] text-white/35">{n}</span><h3 className="mt-16 text-2xl font-medium tracking-[-0.04em]">{title}</h3><p className="mt-4 text-sm leading-6 text-white/50">{body}</p></article>)}</div><div className="mt-16 grid gap-8 border-t border-white/15 pt-8 md:grid-cols-3"><div><div className="metric">8</div><p className="metric-label">execution channels</p></div><div><div className="metric">32</div><p className="metric-label">attack classes in the red-team taxonomy</p></div><div><div className="metric">0</div><p className="metric-label">network calls in the core analyzer</p></div></div></div></section>

        <section id="scenarios" className="mx-auto max-w-[1440px] border-x border-black/10"><div className="grid border-b border-black/10 lg:grid-cols-[.7fr_1.3fr]"><div className="p-6 sm:p-10"><p className="section-index">03 / scenarios that map to real work</p></div><div className="border-t border-black/10 lg:border-l lg:border-t-0">{[["Customer support", "CRM lookup -> internal handoff -> ticket update", "email · address · account ID"], ["Healthcare", "patient record -> summary agent -> generated report", "diagnosis · health ID · DOB"], ["Finance", "account data -> risk agent -> external tool", "card · income · transaction"], ["Human resources", "employee file -> screening agents -> log", "salary · SIN/SSN · address"], ["Multi-agent operations", "planner -> specialist -> reviewer -> shared memory", "credentials · internal IDs · PII"]].map(([name, path, data], i) => <article key={name} className="scenario-row grid gap-3 border-b border-black/10 p-6 sm:grid-cols-[44px_1fr_1.1fr] sm:p-8"><span className="font-mono text-[10px] text-black/35">0{i + 1}</span><div><h3 className="text-lg font-medium tracking-[-0.03em]">{name}</h3><p className="mt-1 text-sm text-black/50">{data}</p></div><p className="font-mono text-xs leading-5 text-black/48">{path}</p></article>)}</div></div></section>

        <section id="evidence" className="mx-auto max-w-[1440px] px-5 py-24 sm:px-8 sm:py-32"><div className="grid gap-16 lg:grid-cols-2"><div><p className="section-index">04 / evidence, not theatre</p><h2 className="mt-8 text-5xl font-medium leading-[.96] tracking-[-0.06em] sm:text-7xl">Built from a measurable privacy gap.</h2></div><div className="grid gap-px self-end border border-black/10 bg-black/10 sm:grid-cols-2"><div className="bg-[#f2f2ef] p-7"><div className="metric text-black">41.7%</div><p className="mt-4 text-sm leading-6 text-black/55">of violations were missed by output-only auditing in the published benchmark.</p></div><div className="bg-[#f2f2ef] p-7"><div className="metric text-black">4,979</div><p className="mt-4 text-sm leading-6 text-black/55">traces across five models and four sensitive domains in the research evaluation.</p></div></div></div><div className="mt-16 grid gap-8 border-t border-black/15 pt-8 text-sm leading-6 text-black/55 md:grid-cols-3"><p><strong className="block text-black">What exists already</strong>Runtime guardrails, agent security platforms and general red-team products cover meaningful parts of this problem.</p><p><strong className="block text-black">AgentLeak's wedge</strong>A local, open-source privacy test focused on internal multi-agent data paths, with deterministic scoring and CI evidence.</p><p><strong className="block text-black">What it does not claim</strong>A passing test is evidence for the tested trace and policy. It is not a legal certification or a guarantee against every future leak.</p></div></section>

        <section className="border-t border-black/10 bg-white"><div className="mx-auto grid max-w-[1440px] gap-10 px-5 py-20 sm:px-8 lg:grid-cols-[1.2fr_.8fr] lg:py-28"><h2 className="text-5xl font-medium leading-[.92] tracking-[-0.065em] sm:text-7xl">Test the channels your users never see.</h2><div className="flex flex-col items-start justify-end"><p className="max-w-md text-sm leading-6 text-black/55">Create a local workspace, run a bundled scenario, then connect a real agent when the baseline makes sense.</p><Link to="/register" className="mt-6 bg-black px-5 py-3 text-sm font-medium text-white transition-transform hover:-translate-y-0.5">Create local workspace</Link></div></div></section>
      </main>

      <footer className="border-t border-white/10 bg-[#101010] text-white"><div className="mx-auto flex max-w-[1440px] flex-col gap-8 px-5 py-10 sm:flex-row sm:items-end sm:justify-between sm:px-8"><div><Wordmark /><p className="mt-3 max-w-sm text-xs leading-5 text-white/40">Local privacy testing for single-agent and multi-agent systems.</p></div><p className="font-mono text-[9px] uppercase tracking-[0.16em] text-white/30">Open source · deterministic · privacy first</p></div></footer>
    </div>
  )
}
