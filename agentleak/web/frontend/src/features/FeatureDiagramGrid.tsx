type DiagramKind =
  | "trace-channels" | "trace-path" | "trace-ledger"
  | "risk-weights" | "risk-formula" | "risk-trend"
  | "code-repository" | "code-flow" | "code-diff"
  | "redteam-matrix" | "redteam-strategies" | "redteam-report"
  | "ci-policy" | "ci-checks" | "ci-attestation"
  | "api-discovery" | "api-scopes" | "api-loop"

type DiagramItem = { label: string; title: string; body: string; kind: DiagramKind }

const DIAGRAMS: Record<string, DiagramItem[]> = {
  "trace-analysis": [
    { label: "NORMALIZED INPUT", title: "Eight channels, one event clock", body: "Align tool calls, memory, logs and outputs on the same ordered trace instead of reviewing separate exports.", kind: "trace-channels" },
    { label: "VALUE PROVENANCE", title: "Follow one value across boundaries", body: "See where sensitive data entered, which agent handled it and the exact event where it escaped.", kind: "trace-path" },
    { label: "AUDITABLE EVIDENCE", title: "Every finding keeps its proof", body: "Channel, timestamp, level and redacted evidence stay attached to the finding for review and replay.", kind: "trace-ledger" },
  ],
  agentrisk: [
    { label: "SEVERITY WEIGHTS", title: "Risk reflects what was exposed", body: "L1 through L4 contribute explicit published weights instead of an unexplained model judgement.", kind: "risk-weights" },
    { label: "DETERMINISTIC SCORE", title: "The calculation is inspectable", body: "Distinct findings and channel exposure resolve into the same score every time the trace is replayed.", kind: "risk-formula" },
    { label: "RELEASE SIGNAL", title: "Read regressions before release", body: "Compare runs against the project boundary and see exactly when risk moves into unsafe territory.", kind: "risk-trend" },
  ],
  "code-scan": [
    { label: "REPOSITORY COVERAGE", title: "Scan the source, not just the diff", body: "Walk supported files, skip generated paths and connect each detected value to an exact file and line.", kind: "code-repository" },
    { label: "SOURCE TO SINK", title: "Map how code can disclose data", body: "Link the read point to logging, tool and third-party sinks so the fix happens at the correct boundary.", kind: "code-flow" },
    { label: "PATCH VERIFICATION", title: "Prove the remediation in the diff", body: "Compare the unsafe call with its redacted replacement and re-score the repository before merge.", kind: "code-diff" },
  ],
  "red-team": [
    { label: "CAMPAIGN MATRIX", title: "Cover attacks and channels together", body: "Measure each attack class against the execution surfaces it can reach instead of counting prompts alone.", kind: "redteam-matrix" },
    { label: "DELIVERY STRATEGIES", title: "Vary how the probe arrives", body: "Replay direct, encoded, jailbreak and multi-turn delivery without changing the vulnerability under test.", kind: "redteam-strategies" },
    { label: "DEFENSE REPORT", title: "Turn probes into engineering work", body: "Rank successful attacks by severity, channel and remediation, then compare defense rate across campaigns.", kind: "redteam-report" },
  ],
  "ci-gate": [
    { label: "POLICY AS CODE", title: "Define the boundary beside the code", body: "Version score thresholds and forbidden channel-level combinations with the project that owns them.", kind: "ci-policy" },
    { label: "REQUIRED CHECK", title: "Block only on a defined crossing", body: "Return a normal pass or fail status that any CI runner and branch protection rule can enforce.", kind: "ci-checks" },
    { label: "SIGNED EVIDENCE", title: "Attach proof to the decision", body: "Keep the policy digest, trace digest and failing finding together so a gate can be audited later.", kind: "ci-attestation" },
  ],
  "agent-api": [
    { label: "MACHINE DISCOVERY", title: "Agents find the contract themselves", body: "Expose llms.txt, the agent card and OpenAPI as stable entry points with no dashboard interpretation required.", kind: "api-discovery" },
    { label: "SCOPED AUTHORITY", title: "Limit every autonomous action", body: "Issue project-bound credentials with explicit test, scan and improve scopes rather than broad account access.", kind: "api-scopes" },
    { label: "BOUNDED LOOP", title: "One fix, one re-test, one delta", body: "Return a structured action, verify the same scenario and stop when policy passes or the iteration budget ends.", kind: "api-loop" },
  ],
}

function DiagramFrame({ title, children }: { title: string; children: React.ReactNode }) {
  return <svg viewBox="0 0 304 232" role="img" aria-label={title}>{children}</svg>
}

function Diagram({ kind, title }: { kind: DiagramKind; title: string }) {
  if (kind === "trace-channels") return <DiagramFrame title={title}>
    <g className="fd-window"><rect x="20" y="25" width="264" height="180" rx="8" /><path d="M20 53h264M91 53v152" /></g>
    <g className="fd-labels"><text x="34" y="72">INPUT</text><text x="34" y="94">TOOLS</text><text x="34" y="116">MEMORY</text><text x="34" y="138">HANDOFF</text><text x="34" y="160">LOGS</text><text x="34" y="182">OUTPUT</text></g>
    <g className="fd-lanes">{[67,89,111,133,155,177].map(y => <path key={y} d={`M102 ${y}h164`} />)}</g>
    <path className="fd-accent-path" d="M108 67h32v44h35v22h38v44h45" />
    <g className="fd-nodes">{[[108,67],[140,111],[175,133],[213,177],[258,177]].map(([x,y],i)=><circle key={i} cx={x} cy={y} r={i===4?4:3} />)}</g>
    <g className="fd-top"><text x="34" y="43">RUN · 01HF7A</text><text x="224" y="43">18 EVENTS</text></g>
  </DiagramFrame>

  if (kind === "trace-path") return <DiagramFrame title={title}>
    <g className="fd-axis"><path d="M35 184h232M54 45v139" /></g>
    <g className="fd-path-nodes">
      <g transform="translate(44 55)"><rect width="62" height="38" rx="6" /><text x="10" y="16">SOURCE</text><text x="10" y="29">vault.email</text></g>
      <g transform="translate(122 96)"><rect width="62" height="38" rx="6" /><text x="10" y="16">AGENT B</text><text x="10" y="29">memory</text></g>
      <g transform="translate(200 137)"><rect width="62" height="38" rx="6" /><text x="10" y="16">SINK · L3</text><text x="10" y="29">tool_call</text></g>
    </g>
    <path className="fd-accent-path fd-dashed" d="M106 74c27 0 0 41 16 41h62c27 0 0 41 16 41" />
    <g className="fd-event-ticks"><path d="M74 184v8M153 184v8M231 184v8" /><text x="62" y="205">10:42.01</text><text x="141" y="205">10:42.18</text><text x="219" y="205">10:42.31</text></g>
  </DiagramFrame>

  if (kind === "trace-ledger") return <DiagramFrame title={title}>
    <g className="fd-window"><rect x="22" y="28" width="260" height="176" rx="8" /><path d="M22 58h260M22 91h260M22 124h260M22 157h260" /></g>
    <g className="fd-top"><text x="36" y="47">FINDINGS</text><text x="236" y="47">LEVEL</text></g>
    <g className="fd-ledger">{[["tool_call","customer.email","L4"],["shared_memory","patient.id","L3"],["logs","session.token","L4"],["final_output","—","PASS"]].map(([a,b,c],i)=><g key={a} transform={`translate(0 ${i*33})`}><circle cx="39" cy="75" r="3"/><text x="51" y="78">{a}</text><text x="148" y="78">{b}</text><text className={c==="PASS"?"fd-pass":"fd-alert"} x="244" y="78">{c}</text></g>)}</g>
    <g className="fd-footer"><text x="36" y="190">digest · a91c…e204</text><path d="M205 187h56" /></g>
  </DiagramFrame>

  if (kind === "risk-weights") return <DiagramFrame title={title}>
    <g className="fd-chart-axis"><path d="M42 189h225M42 35v154" /></g>
    <g className="fd-weight-bars">{[[70,44,"L1","0.08"],[120,78,"L2","0.18"],[170,116,"L3","0.31"],[220,158,"L4","0.43"]].map(([x,h,l,w])=><g key={l}><rect x={x as number} y={189-(h as number)} width="28" height={h as number} rx="3"/><text x={(x as number)+7} y="205">{l}</text><text x={(x as number)+4} y={181-(h as number)}>{w}</text></g>)}</g>
    <text className="fd-caption" x="42" y="26">PUBLISHED SEVERITY CONTRIBUTION</text>
  </DiagramFrame>

  if (kind === "risk-formula") return <DiagramFrame title={title}>
    <g className="fd-formula-card"><rect x="28" y="35" width="248" height="157" rx="8" /><text x="43" y="57">AGENTRISK · RUN 208</text>
      <g transform="translate(43 76)"><rect width="51" height="42" rx="5"/><text x="9" y="17">L4 × 2</text><text x="9" y="32">0.62</text></g>
      <text className="fd-operator" x="103" y="102">+</text>
      <g transform="translate(120 76)"><rect width="51" height="42" rx="5"/><text x="9" y="17">L2 × 1</text><text x="9" y="32">0.11</text></g>
      <text className="fd-operator" x="180" y="102">→</text>
      <g className="fd-result" transform="translate(198 70)"><rect width="60" height="54" rx="5"/><text x="12" y="18">RISK</text><text x="12" y="40">0.73</text></g>
      <path d="M43 141h215"/><text x="43" y="159">privacy score</text><text className="fd-score" x="231" y="159">27 / 100</text><path className="fd-meter" d="M43 176h150"/><path className="fd-meter-value" d="M43 176h41"/>
    </g>
  </DiagramFrame>

  if (kind === "risk-trend") return <DiagramFrame title={title}>
    <g className="fd-chart-axis"><path d="M35 191h243M35 32v159" />{[65,105,145].map(y=><path key={y} d={`M35 ${y}h243`}/>)}</g>
    <path className="fd-threshold" d="M35 102h243"/><text className="fd-alert" x="224" y="96">POLICY .40</text>
    <path className="fd-area" d="M36 176 70 169 103 154 136 147 169 118 202 126 235 82 268 69v122H36Z"/>
    <path className="fd-accent-path" d="M36 176 70 169 103 154 136 147 169 118 202 126 235 82 268 69"/>
    <g className="fd-nodes"><circle cx="202" cy="126" r="3"/><circle className="fd-alert-node" cx="235" cy="82" r="4"/><circle className="fd-alert-node" cx="268" cy="69" r="4"/></g>
    <g className="fd-event-ticks"><text x="35" y="208">v1.4</text><text x="132" y="208">v1.8</text><text x="247" y="208">v2.1</text></g>
  </DiagramFrame>

  if (kind === "code-repository") return <DiagramFrame title={title}>
    <g className="fd-window"><rect x="21" y="27" width="262" height="178" rx="8"/><path d="M21 56h262M94 56v149"/></g>
    <g className="fd-top"><text x="35" y="46">REPOSITORY · main</text><text x="235" y="46">142 FILES</text></g>
    <g className="fd-labels"><text x="35" y="79">src/</text><text x="43" y="99">agent.py</text><text x="43" y="119">tools.py</text><text x="43" y="139">memory.py</text><text x="35" y="166">tests/</text></g>
    <g className="fd-code-lines">{[[110,76,82],[110,95,124],[110,114,98],[110,133,139],[110,152,68],[110,171,117]].map(([x,y,w],i)=><g key={y}><text x="103" y={(y as number)+3}>{38+i}</text><path className={i===3?"fd-alert-stroke":""} d={`M${x} ${y}h${w}`}/></g>)}</g>
    <g className="fd-finding-pill"><rect x="188" y="122" width="78" height="27" rx="5"/><text x="198" y="139">L4 · line 41</text></g>
  </DiagramFrame>

  if (kind === "code-flow") return <DiagramFrame title={title}>
    <path className="fd-flow-rail" d="M34 115h236"/>
    <g className="fd-flow-boxes">{[[28,"READ","vault.email"],[119,"GUARD","redact()"],[210,"SINK","crm.send"]].map(([x,a,b],i)=><g key={a} transform={`translate(${x} 79)`}><rect width="66" height="72" rx="7"/><text className="fd-card-title" x="12" y="22">{a}</text><text x="12" y="43">{b}</text>{i===1&&<path className="fd-check" d="m24 57 6 6 13-16"/>}</g>)}</g>
    <g className="fd-flow-arrows"><path d="M94 115h25M112 110l7 5-7 5M185 115h25M203 110l7 5-7 5"/></g>
    <g className="fd-flow-meta"><text x="28" y="170">source</text><text x="119" y="170">policy boundary</text><text x="210" y="170">third party</text></g>
  </DiagramFrame>

  if (kind === "code-diff") return <DiagramFrame title={title}>
    <g className="fd-window"><rect x="29" y="29" width="246" height="174" rx="8"/><path d="M29 58h246"/></g>
    <g className="fd-top"><text x="43" y="48">PATCH · agent.py</text><text x="224" y="48">1 / 1</text></g>
    <g className="fd-diff"><rect className="fd-remove-bg" x="37" y="77" width="230" height="36"/><text className="fd-alert" x="48" y="91">− 41</text><text x="79" y="91">crm.send(customer.email)</text><path d="M79 100h133"/>
      <rect className="fd-add-bg" x="37" y="119" width="230" height="36"/><text className="fd-pass" x="48" y="133">+ 41</text><text x="79" y="133">crm.send(redact(email))</text><path d="M79 142h119"/>
      <text x="48" y="177">code privacy score</text><text className="fd-score" x="222" y="177">62 → 94</text><path className="fd-meter" d="M48 188h176"/><path className="fd-meter-value" d="M48 188h165"/></g>
  </DiagramFrame>

  if (kind === "redteam-matrix") return <DiagramFrame title={title}>
    <g className="fd-window"><rect x="24" y="25" width="256" height="181" rx="8"/><path d="M24 54h256M93 54v152"/></g>
    <g className="fd-top"><text x="38" y="44">CAMPAIGN 07</text><text x="228" y="44">12 TESTS</text></g>
    <g className="fd-matrix-labels"><text x="38" y="82">PROMPT</text><text x="38" y="114">ENCODE</text><text x="38" y="146">TOOL</text><text x="38" y="178">HANDOFF</text><text x="108" y="66">IN</text><text x="150" y="66">TOOL</text><text x="196" y="66">MEM</text><text x="245" y="66">OUT</text></g>
    <g className="fd-matrix-lines">{[83,115,147,179].map(y=><path key={y} d={`M93 ${y}h187`}/>)}{[116,160,207,253].map(x=><path key={x} d={`M${x} 70v136`}/>)}</g>
    <g className="fd-matrix-dots">{Array.from({length:16},(_,i)=><g key={i} className={i%3===1||i===11?"blocked":"pass"}><circle cx={107+(i%4)*46} cy={82+Math.floor(i/4)*32} r="5"/>{(i%3===1||i===11)&&<path d={`m${104+(i%4)*46} ${82+Math.floor(i/4)*32} 2.5 2.5 5-6`}/>}</g>)}</g>
  </DiagramFrame>

  if (kind === "redteam-strategies") return <DiagramFrame title={title}>
    <g className="fd-strategy-source"><rect x="24" y="84" width="72" height="63" rx="7"/><text x="38" y="104">PLUGIN</text><text x="38" y="124">pii:direct</text></g>
    <path className="fd-flow-rail" d="M96 115h36M132 115c22 0 12-67 32-67M132 115h32M132 115c22 0 12 67 32 67"/>
    <g className="fd-strategy-cards">{[[164,25,"DIRECT","baseline"],[164,84,"ENCODE","base64"],[164,143,"MULTI-TURN","crescendo"]].map(([x,y,a,b],i)=><g key={a} transform={`translate(${x} ${y})`} className={i===1?"active":""}><rect width="112" height="48" rx="6"/><text className="fd-card-title" x="13" y="19">{a}</text><text x="13" y="35">{b}</text><circle cx="96" cy="24" r="4"/></g>)}</g>
  </DiagramFrame>

  if (kind === "redteam-report") return <DiagramFrame title={title}>
    <g className="fd-window"><rect x="24" y="26" width="256" height="180" rx="8"/><path d="M24 57h256"/></g><g className="fd-top"><text x="38" y="46">DEFENSE REPORT</text><text x="237" y="46">v.07</text></g>
    <g className="fd-big-score"><text x="39" y="89">DEFENSE RATE</text><text x="39" y="120">75%</text><path className="fd-meter" d="M39 136h102"/><path className="fd-meter-value" d="M39 136h76"/></g>
    <g className="fd-report-bars">{[["prompt",3],["tools",7],["memory",5],["handoff",2]].map(([a,v],i)=><g key={a} transform={`translate(161 ${78+i*29})`}><text x="0" y="7">{a}</text><path d="M48 4h57"/><path className={Number(v)>5?"fd-alert-stroke":"fd-accent-stroke"} d={`M48 4h${Number(v)*7}`}/><text x="111" y="7">{v}</text></g>)}</g>
    <text className="fd-alert" x="39" y="179">3 successful attacks</text><text x="39" y="194">2 remediations ready</text>
  </DiagramFrame>

  if (kind === "ci-policy") return <DiagramFrame title={title}>
    <g className="fd-window"><rect x="29" y="28" width="246" height="175" rx="8"/><path d="M29 57h246"/></g><g className="fd-top"><text x="43" y="47">agentleak.yaml</text><text x="239" y="47">POLICY</text></g>
    <g className="fd-policy-code"><text x="45" y="79">minimum_score:</text><text className="fd-score" x="197" y="79">80</text><text x="45" y="104">block:</text><text x="61" y="127">channel: tool_call</text><text x="61" y="148">at_or_above: L3</text><text x="45" y="177">require_trace_digest:</text><text className="fd-pass" x="229" y="177">true</text></g>
    <path className="fd-indent" d="M52 111v43"/>
  </DiagramFrame>

  if (kind === "ci-checks") return <DiagramFrame title={title}>
    <g className="fd-pr-header"><text x="28" y="34">PR #284 · privacy checks</text><path d="M28 45h248"/></g>
    <g className="fd-check-list">{[["unit tests","1m 08s","pass"],["agentleak / trace","18s","fail"],["agentleak / code","11s","pass"],["build","52s","wait"]].map(([a,b,c],i)=><g key={a} transform={`translate(28 ${62+i*39})`} className={c}><rect width="248" height="32" rx="6"/><circle cx="17" cy="16" r="6"/>{c==="pass"&&<path d="m14 16 2 2 4-5"/>}{c==="fail"&&<path d="m14 13 6 6m0-6-6 6"/>}<text x="33" y="19">{a}</text><text x="207" y="19">{b}</text></g>)}</g>
  </DiagramFrame>

  if (kind === "ci-attestation") return <DiagramFrame title={title}>
    <g className="fd-attestation-chain">{[[31,"POLICY","9d31…aa"],[119,"TRACE","b807…f2"],[207,"REPORT","e204…19"]].map(([x,a,b],i)=><g key={a} transform={`translate(${x} 76)`}><path d="m0 16 33-16 33 16v54L33 86 0 70Z"/><path d="m0 16 33 17 33-17M33 33v53"/><text x="12" y="48">{a}</text><text x="12" y="62">{b}</text>{i<2&&<path className="fd-chain-link" d="M66 43h22"/>}</g>)}</g>
    <g className="fd-attestation-footer"><path d="M31 184h242"/><circle cx="44" cy="199" r="6"/><path className="fd-check" d="m41 199 2 2 4-5"/><text x="58" y="202">decision signed · 2026-07-20 18:42 UTC</text></g>
  </DiagramFrame>

  if (kind === "api-discovery") return <DiagramFrame title={title}>
    <g className="fd-api-root"><circle cx="63" cy="116" r="31"/><text x="42" y="113">AGENT</text><text x="45" y="127">client</text></g>
    <path className="fd-flow-rail" d="M94 116h35M129 116c20 0 15-61 35-61M129 116h35M129 116c20 0 15 61 35 61"/>
    <g className="fd-endpoints">{[[164,32,"/llms.txt","instructions"],[164,93,"/.well-known","agent card"],[164,154,"/openapi.json","contract"]].map(([x,y,a,b],i)=><g key={a} transform={`translate(${x} ${y})`} className={i===0?"active":""}><rect width="117" height="47" rx="6"/><text className="fd-card-title" x="12" y="18">{a}</text><text x="12" y="34">{b}</text><circle cx="101" cy="24" r="4"/></g>)}</g>
  </DiagramFrame>

  if (kind === "api-scopes") return <DiagramFrame title={title}>
    <g className="fd-token"><rect x="34" y="40" width="236" height="151" rx="8"/><text className="fd-card-title" x="51" y="62">PROJECT KEY · alk_live_••••7f2</text><path d="M34 75h236"/>
      <text x="51" y="96">project</text><text className="fd-score" x="207" y="96">support-bot</text><text x="51" y="119">expires</text><text x="207" y="119">30 days</text><text x="51" y="145">scopes</text>
      <g className="fd-scope-pills"><g transform="translate(97 132)"><rect width="43" height="22" rx="11"/><text x="10" y="14">test</text></g><g transform="translate(145 132)"><rect width="43" height="22" rx="11"/><text x="10" y="14">scan</text></g><g transform="translate(193 132)"><rect width="58" height="22" rx="11"/><text x="9" y="14">improve</text></g></g>
      <circle cx="55" cy="172" r="6"/><path className="fd-check" d="m52 172 2 2 4-5"/><text x="68" y="175">account access denied by design</text>
    </g>
  </DiagramFrame>

  return <DiagramFrame title={title}>
    <path className="fd-loop-path" d="M66 73c28-39 75-48 116-28 42 21 62 66 47 108-14 41-57 66-100 57-44-9-73-48-69-90"/>
    <g className="fd-loop-cards"><g transform="translate(26 62)"><rect width="78" height="55" rx="7"/><text className="fd-card-title" x="12" y="19">SELF-TEST</text><text x="12" y="37">risk 0.74</text></g><g transform="translate(113 25)"><rect width="78" height="55" rx="7"/><text className="fd-card-title" x="12" y="19">IMPROVE</text><text x="12" y="37">1 action</text></g><g className="active" transform="translate(200 98)"><rect width="78" height="55" rx="7"/><text className="fd-card-title" x="12" y="19">VERIFY</text><text x="12" y="37">risk 0.08</text></g></g>
    <g className="fd-loop-center"><circle cx="145" cy="133" r="31"/><text x="126" y="130">DELTA</text><text className="fd-score" x="126" y="146">−0.66</text></g>
    <g className="fd-loop-arrow"><path d="m226 174-3-9 9 2"/><path d="m66 73 9-1-3 8"/></g>
  </DiagramFrame>
}

export function FeatureDiagramGrid({ slug }: { slug: string }) {
  const items = DIAGRAMS[slug]
  if (!items) return null
  return <section className="feature-diagrams" aria-labelledby={`${slug}-visuals-title`}>
    <header><p className="cursor-eyebrow">Inside the capability</p><h2 id={`${slug}-visuals-title`}>Three views of how it works.</h2></header>
    <div className="feature-diagrams-grid">
      {items.map((item) => <article key={item.kind}>
        <span>{item.label}</span>
        <div className="feature-diagram-visual"><Diagram kind={item.kind} title={item.title} /></div>
        <h3>{item.title}</h3><p>{item.body}</p>
      </article>)}
    </div>
  </section>
}
