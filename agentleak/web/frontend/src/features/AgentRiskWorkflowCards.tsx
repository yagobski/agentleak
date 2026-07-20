import { useEffect, useState } from "react"

export function AgentRiskWorkflowCards() {
  const [visuals, setVisuals] = useState<string[]>([])

  useEffect(() => {
    let active = true
    fetch("/assets/brand/agentrisk-workflows.html")
      .then((response) => response.text())
      .then((source) => {
        const document = new DOMParser().parseFromString(source, "text/html")
        const figures = Array.from(document.querySelectorAll("figure")).slice(0, 2)
        const exactVisuals = figures.map((figure) => figure.querySelector('svg[viewBox="0 0 672 424"]')?.outerHTML ?? "")
        if (active && exactVisuals.every(Boolean)) setVisuals(exactVisuals)
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  return (
    <section className="workflow-section agentrisk-workflow-section" aria-labelledby="agentrisk-workflow-title">
      <header>
        <p className="cursor-eyebrow">AgentRisk over time</p>
        <h2 id="agentrisk-workflow-title">Turn every run into a measurable release signal.</h2>
      </header>
      <div className="workflow-cards">
        <article>
          <div className="agentrisk-workflow-visual" role="img" aria-label="Privacy milestones and policy dependencies across releases" dangerouslySetInnerHTML={{ __html: visuals[0] ?? "" }} />
          <div className="workflow-caption">
            <h3>Risk milestones and policy dependencies</h3>
            <p>Map score thresholds, privacy gates and remediation dependencies across releases so the critical path to a safe deployment stays visible.</p>
          </div>
        </article>
        <article>
          <div className="agentrisk-workflow-visual" role="img" aria-label="AgentRisk trend and projected privacy policy boundary" dangerouslySetInnerHTML={{ __html: visuals[1] ?? "" }} />
          <div className="workflow-caption">
            <h3>Predict privacy outcomes</h3>
            <p>Read AgentRisk trends, exposure volume and policy thresholds together to see when a release is approaching unsafe territory.</p>
          </div>
        </article>
      </div>
    </section>
  )
}
