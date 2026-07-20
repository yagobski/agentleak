import { useEffect, useState } from "react"

const USER_LOGOS = ["Vercel", "Cursor", "Oscar", "OpenAI", "Coinbase", "Cash App", "Boom", "Ramp"] as const

function LogoTrack({ logos, hidden = false }: { logos: string[]; hidden?: boolean }) {
  return (
    <div className="user-logo-track" aria-hidden={hidden || undefined}>
      {logos.map((markup, index) => (
        <span
          key={`${USER_LOGOS[index]}-${hidden ? "duplicate" : "primary"}`}
          role={hidden ? undefined : "img"}
          aria-label={hidden ? undefined : USER_LOGOS[index]}
          dangerouslySetInnerHTML={{ __html: markup }}
        />
      ))}
    </div>
  )
}

export function UserLogoStrip() {
  const [logos, setLogos] = useState<string[]>([])

  useEffect(() => {
    let active = true
    fetch("/assets/brand/agentleak-users.html")
      .then((response) => response.text())
      .then((markup) => {
        const document = new DOMParser().parseFromString(markup, "text/html")
        const exactLogos = Array.from(document.querySelectorAll("svg"), (svg) => svg.outerHTML).slice(0, USER_LOGOS.length)
        if (active && exactLogos.length === USER_LOGOS.length) setLogos(exactLogos)
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  return (
    <section className="user-logo-section" aria-labelledby="user-logo-title">
      <h2 id="user-logo-title">Used by teams building the next generation of agents</h2>
      {logos.length === USER_LOGOS.length ? (
        <div className="user-logo-marquee">
          <LogoTrack logos={logos} />
          <LogoTrack logos={logos} hidden />
        </div>
      ) : <div className="user-logo-loading" aria-hidden="true" />}
    </section>
  )
}
