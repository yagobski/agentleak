import { Link } from "react-router-dom"
import { Arrow } from "@/features/ProductDemos"

function StackVisual() {
  return (
    <svg className="principle-stack" viewBox="0 0 265 262" role="img" aria-label="Eight agent execution channels stacked into one auditable trace">
      {[186.583, 168.583, 150.583, 132.583, 114.583].map((y, index) => (
        <path key={y} className={`principle-stack-layer layer-${index}`} d={`m19.107 ${y} 108.543 54.272a10.29 10.29 0 0 0 9.2 0l108.543-54.272`} />
      ))}
      <path className="principle-stack-shell" d="M250.355 107.636a3.43 3.43 0 0 1 1.895 3.067v88.333a3.43 3.43 0 0 1-1.895 3.067l-111.972 55.985a13.71 13.71 0 0 1-12.266 0L14.145 202.103a3.43 3.43 0 0 1-1.895-3.067v-88.333c0-1.299.734-2.486 1.895-3.067l115.038-57.52a6.86 6.86 0 0 1 6.134 0z" />
      <g className="principle-stack-top">
        <path className="principle-surface" d="M250.355 66.493a3.43 3.43 0 0 1 1.895 3.067v9.476a3.43 3.43 0 0 1-1.895 3.067L136.85 138.855a10.29 10.29 0 0 1-9.2 0L14.145 82.103a3.43 3.43 0 0 1-1.895-3.067V69.56c0-1.299.734-2.486 1.895-3.067L129.183 8.974a6.86 6.86 0 0 1 6.134 0z" />
        <path className="principle-detail" d="m19.107 71.726 108.543 54.272a10.29 10.29 0 0 0 9.2 0l108.543-54.272" />
        <path className="principle-detail" d="M103.378 91.627c-.908-.281-.495-.95.573-.95h56.598c1.068 0 1.48.669.573.95-17.631 5.466-40.113 5.466-57.744 0ZM91.088 86.43c.205.117.502.183.813.183h80.697c.311 0 .608-.066.814-.182a42 42 0 0 0 4.679-3.057c.47-.357-.052-.824-.907-.824H87.316c-.856 0-1.378.467-.907.824a42 42 0 0 0 4.679 3.057ZM81.032 78.14c.16.21.564.346 1.013.346h100.409c.449 0 .853-.136 1.014-.346q1.152-1.502 1.939-3.05c.173-.34-.349-.667-1.052-.667H80.145c-.704 0-1.226.327-1.052.668a19.7 19.7 0 0 0 1.938 3.05ZM78.564 70.36c-.574 0-1.052-.222-1.084-.508-.849-7.528 4.478-15.198 15.98-20.95 21.423-10.71 56.157-10.71 77.58 0 11.502 5.752 16.828 13.422 15.979 20.95-.032.286-.51.507-1.084.507z" />
      </g>
      <g className="principle-guides">
        <path d="M12.679 84.584v20.142" /><path d="M132.25 144.583v20.143" /><path d="M251.821 84.584v20.142" />
      </g>
    </svg>
  )
}

function DotGrid({ x, y, delay }: { x: number; y: number; delay: number }) {
  return (
    <g className="principle-dot-grid" transform={`translate(${x} ${y})`} style={{ "--dot-delay": `${delay}s` } as React.CSSProperties}>
      {Array.from({ length: 25 }, (_, index) => (
        <circle key={index} cx={(index % 5) * 3.5 + 1} cy={Math.floor(index / 5) * 3.5 + 1} r="1" style={{ "--dot-index": index } as React.CSSProperties} />
      ))}
    </g>
  )
}

function AgentVisual() {
  return (
    <svg className="principle-agents" viewBox="0 0 304 281" role="img" aria-label="Multiple agents exchanging privacy evidence across a shared system">
      <g className="agent-node agent-node-back">
        <path d="M148.534 1.068a7.75 7.75 0 0 1 6.932 0l50.211 25.106a3.75 3.75 0 0 1 2.073 3.354v125.056c0 1.42-.803 2.718-2.073 3.354l-50.211 25.105a7.75 7.75 0 0 1-6.932 0l-50.21-25.105a3.75 3.75 0 0 1-2.074-3.354V29.528a3.75 3.75 0 0 1 2.073-3.354z" />
        <path className="principle-detail" d="m102 30.056 46.422 23.21a8 8 0 0 0 7.156 0L202 30.057" />
        <DotGrid x={144} y={18} delay={0.2} />
      </g>
      <g className="agent-node agent-node-low">
        <path d="M84.534 139.068a7.76 7.76 0 0 1 6.932 0l50.211 25.106a3.75 3.75 0 0 1 2.073 3.353v19.057c0 1.42-.803 2.718-2.073 3.354l-50.211 25.105a7.75 7.75 0 0 1-6.932 0l-50.21-25.105a3.75 3.75 0 0 1-2.074-3.354v-19.057a3.75 3.75 0 0 1 2.073-3.353z" />
        <path className="principle-detail" d="m38 168.056 46.422 23.211a8 8 0 0 0 7.156 0L138 168.056" />
      </g>
      <g className="agent-node agent-node-left">
        <path d="M84.534 53.069a7.75 7.75 0 0 1 6.932 0l50.211 25.105a3.75 3.75 0 0 1 2.073 3.353v73.057c0 1.42-.803 2.718-2.073 3.354l-50.211 25.105a7.75 7.75 0 0 1-6.932 0l-50.21-25.105a3.75 3.75 0 0 1-2.074-3.354V81.528a3.75 3.75 0 0 1 2.073-3.354z" />
        <path className="principle-detail" d="m38 82.056 46.422 23.211a8 8 0 0 0 7.156 0L138 82.056" />
        <DotGrid x={80} y={68} delay={0} />
      </g>
      <g className="agent-node agent-node-right-low">
        <path d="M212.534 97.069a7.75 7.75 0 0 1 6.932 0l50.211 25.105a3.75 3.75 0 0 1 2.073 3.353v61.057c0 1.42-.803 2.718-2.073 3.354l-50.211 25.105a7.75 7.75 0 0 1-6.932 0l-50.211-25.105a3.75 3.75 0 0 1-2.073-3.354v-61.057a3.75 3.75 0 0 1 2.073-3.353z" />
        <path className="principle-detail" d="m166 126.056 46.422 23.211a8 8 0 0 0 7.156 0L266 126.056" />
      </g>
      <g className="agent-node agent-node-right">
        <path d="M212.534 64.069a7.75 7.75 0 0 1 6.932 0l50.211 25.105a3.75 3.75 0 0 1 2.073 3.353v19.057c0 1.42-.803 2.718-2.073 3.354l-50.211 25.105a7.75 7.75 0 0 1-6.932 0l-50.211-25.105a3.75 3.75 0 0 1-2.073-3.354V92.528a3.75 3.75 0 0 1 2.073-3.354z" />
        <path className="principle-detail" d="m166 93.056 46.422 23.211a8 8 0 0 0 7.156 0L266 93.056" />
        <DotGrid x={208} y={78} delay={0.4} />
      </g>
      <g className="agent-node agent-node-front">
        <path d="M148.534 145.068a7.76 7.76 0 0 1 6.932 0l50.211 25.106a3.75 3.75 0 0 1 2.073 3.353v45.057c0 1.42-.803 2.718-2.073 3.354l-50.211 25.105a7.75 7.75 0 0 1-6.932 0l-50.21-25.105a3.75 3.75 0 0 1-2.074-3.354v-45.057a3.75 3.75 0 0 1 2.073-3.353z" />
        <path className="principle-detail" d="m102 174.056 46.422 23.211a8 8 0 0 0 7.156 0L202 174.056" />
        <DotGrid x={144} y={160} delay={0.6} />
      </g>
    </svg>
  )
}

const MOMENTUM_PANELS = [
  [137.044, 107.668, 20.529], [128.594, 98.378, 34.049], [120.144, 82.316, 54.331],
  [111.694, 59.504, 81.373], [103.244, 16.4, 128.697], [94.794, 67.954, 81.373],
  [86.344, 99.216, 54.331], [77.894, 123.728, 34.049], [69.444, 141.478, 20.529],
  [60.994, 152.459, 13.768], [52.544, 160.06, 10.387], [44.094, 165.979, 8.698],
  [35.634, 171.055, 7.852], [27.184, 175.274, 7.853], [18.734, 179.504, 7.853],
] as const

function MomentumVisual() {
  return (
    <svg className="principle-momentum" viewBox="0 0 272 267" role="img" aria-label="A fast sequence of deterministic privacy checks moving toward release">
      {MOMENTUM_PANELS.map(([x, y, height], index) => {
        const topX = x + 0.645
        const topY = y + 2.778
        const sideHeight = height - 2.336
        return (
          <g className="momentum-panel" key={`${x}-${y}`} style={{ "--panel-index": index } as React.CSSProperties}>
            <path d={`M${x} ${y}a1.44 1.44 0 0 1 1.288 0l115.686 57.843a3.13 3.13 0 0 1 1.73 2.8v${height}a1.44 1.44 0 0 1-.796 1.288l-1.69.845a1.44 1.44 0 0 1-1.288 0L${x - 1.256} ${y + 57.843}a3.13 3.13 0 0 1-1.73-2.8V${y + 2.133}c0-.545.308-1.044.796-1.288z`} />
            <path className="principle-detail" d={`M${topX} ${topY}l113.061 56.531a3.38 3.38 0 0 1 1.868 3.023v${sideHeight}`} />
          </g>
        )
      })}
    </svg>
  )
}

const PRINCIPLES = [
  {
    figure: "FIG 0.1",
    title: "Every execution channel, one trace",
    body: "Audit tool calls, responses, memory, agent handoffs, logs, files and the final answer as one evidence chain.",
    href: "/features/trace-analysis",
    visual: <StackVisual />,
  },
  {
    figure: "FIG 0.2",
    title: "Built for multi-agent systems",
    body: "See which agent received a secret, where it crossed a boundary and which handoff needs a guard.",
    href: "/use-cases/multi-agent-privacy",
    visual: <AgentVisual />,
  },
  {
    figure: "FIG 0.3",
    title: "Deterministic enough for CI",
    body: "Replay the same trace, get the same score and block a release only when a defined privacy policy is crossed.",
    href: "/features/ci-gate",
    visual: <MomentumVisual />,
  },
] as const

export function FeaturePrinciples() {
  return (
    <section className="principles-section" aria-labelledby="principles-title">
      <header>
        <p className="cursor-eyebrow">Designed for agent privacy engineering</p>
        <h2 id="principles-title">See the system your output-only checks cannot.</h2>
        <p>AgentLeak turns the hidden execution path into evidence teams and agents can inspect, compare and enforce.</p>
      </header>
      <div className="principles-grid">
        {PRINCIPLES.map((item) => (
          <article key={item.figure}>
            <span>{item.figure}</span>
            <div className="principle-visual">{item.visual}</div>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
            <Link to={item.href}>Explore the capability <Arrow /></Link>
          </article>
        ))}
      </div>
    </section>
  )
}
