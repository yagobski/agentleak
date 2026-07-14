import { Link } from "react-router-dom"
import { Arrow } from "@/features/ProductDemos"
import {
  FAQ_GROUPS,
  FaqItem,
  REPO_URL,
  SiteFooter,
  SiteNav,
  usePageMeta,
} from "@/features/SiteChrome"

export function Faq() {
  usePageMeta(
    "FAQ · AgentLeak",
    "Short answers to common questions about AgentLeak: open source, how it differs from guardrails, what AgentRisk is, local detection, supported frameworks and the free agent tier.",
  )
  return (
    <div className="cursor-site">
      <SiteNav />
      <main>
        <section className="cursor-page">
          <div className="cursor-page-hero">
            <p className="cursor-eyebrow">FAQ</p>
            <h1>Questions, answered.</h1>
            <p>
              The short version of how AgentLeak works, what it costs, and how it differs from a
              guardrail or a red-team prompt. Need more depth? The documentation covers every
              endpoint and concept.
            </p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/docs">Read the documentation <Arrow /></Link>
              <a className="cursor-button cursor-button-light" href={REPO_URL}>View source <Arrow /></a>
            </div>
          </div>
        </section>

        {FAQ_GROUPS.map((group) => (
          <section className="cursor-faq cursor-faq-group" key={group.title}>
            <header><h2>{group.title}</h2></header>
            <div className="cursor-faq-list">
              {group.items.map(([q, a]) => <FaqItem key={q} q={q} a={a} />)}
            </div>
          </section>
        ))}

        <section className="cursor-final-cta">
          <div className="cursor-final-inner">
            <p className="cursor-eyebrow">Still curious?</p>
            <h2>The fastest answer is a run.</h2>
            <p>Create a local workspace, score a bundled scenario, and see the report for yourself in a couple of minutes.</p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Start testing AgentLeak <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/research">See the research <Arrow /></Link>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}
