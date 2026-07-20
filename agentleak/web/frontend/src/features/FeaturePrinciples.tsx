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
        <path className="principle-agentleak-mark" transform="translate(109 28) scale(.18)" d="M254.055 120.935C254.055 120.935 221.678 112.525 189.301 99.4902C160.288 87.7168 136.32 73 136.32 73C136.32 73 112.773 88.1373 83.3397 99.4902C51.3832 112.525 19.0062 120.514 18.5857 120.935C16.0629 135.231 14.8014 150.368 14.8014 165.506C14.8014 168.869 14.8014 170.551 15.2219 173.915C16.9038 191.996 48.8603 183.166 60.2133 178.961C61.4747 178.54 63.1566 177.7 64.4181 177.279C68.6229 175.597 72.8277 173.915 77.4529 171.813C86.283 168.028 95.5336 163.403 105.205 158.357C119.08 150.789 133.377 142.379 145.571 132.708C127.49 157.096 88.8059 186.109 45.4965 204.61C34.564 209.236 19.4267 215.122 8.91471 214.702C-3.69969 214.281 0.505106 216.384 1.34607 216.804C14.8014 223.532 22.3701 233.203 26.1544 242.033C28.6773 247.92 37.5073 257.17 85.0216 232.782C111.932 218.907 146.412 199.144 181.312 171.392C182.573 170.551 183.834 169.29 185.096 168.449C192.664 162.142 200.654 155.835 208.222 149.107C190.142 185.689 139.264 228.157 77.8734 259.693C58.5313 269.785 53.4856 271.046 45.076 273.989C33.723 277.774 22.7905 276.092 22.7905 278.194C22.3701 281.138 37.0869 284.081 52.2242 299.218C66.1 313.094 101 297.116 115.717 289.127C132.115 279.876 161.549 261.375 181.312 244.135C185.096 240.772 188.46 237.408 191.824 234.044C177.107 268.944 145.571 294.172 103.943 317.719C93.4312 323.606 75.771 328.652 68.2024 330.754C66.1 331.595 63.1566 331.595 63.1566 332.857C63.1566 335.38 79.9758 337.061 90.9083 342.948C106.046 350.937 116.558 355.142 120.342 356.404C125.388 358.506 130.854 359.767 136.32 361.029C208.643 345.051 257.418 262.216 257.418 165.085C257.839 150.368 256.577 135.231 254.055 120.935Z" />
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
    figure: "8 EXECUTION CHANNELS",
    title: "Every execution channel, one trace",
    body: "Audit tool calls, responses, memory, agent handoffs, logs, files and the final answer as one evidence chain.",
    href: "/features/trace-analysis",
    visual: <StackVisual />,
  },
  {
    figure: "AGENT PROVENANCE",
    title: "Built for multi-agent systems",
    body: "See which agent received a secret, where it crossed a boundary and which handoff needs a guard.",
    href: "/use-cases/multi-agent-privacy",
    visual: <AgentVisual />,
  },
  {
    figure: "DETERMINISTIC CI GATE",
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
