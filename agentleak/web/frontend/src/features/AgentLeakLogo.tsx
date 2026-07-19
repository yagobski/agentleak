type AgentLeakLogoProps = {
  className?: string
  label?: string
}

export function AgentLeakLogo({ className = "", label = "AgentLeak" }: AgentLeakLogoProps) {
  return (
    <span
      className={`agentleak-logo ${className}`.trim()}
      role={label ? "img" : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : "true"}
    >
      <img
        className="agentleak-logo-on-light"
        src="/assets/logo/agentleak-logo-dark.svg"
        alt=""
        draggable="false"
      />
      <img
        className="agentleak-logo-on-dark"
        src="/assets/logo/agentleak-logo-white.svg"
        alt=""
        draggable="false"
      />
    </span>
  )
}

export function AgentLeakMark({ className = "", label = "AgentLeak" }: AgentLeakLogoProps) {
  return (
    <span
      className={`agentleak-mark ${className}`.trim()}
      role={label ? "img" : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : "true"}
    >
      <img className="agentleak-mark-on-light" src="/assets/logo/agentleak-logo-dark.svg" alt="" draggable="false" />
      <img className="agentleak-mark-on-dark" src="/assets/logo/agentleak-logo-white.svg" alt="" draggable="false" />
    </span>
  )
}
