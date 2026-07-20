const USER_LOGOS = ["Vercel", "Cursor", "Oscar", "OpenAI", "Coinbase", "Cash App", "Boom", "Ramp"] as const

function UserLogo({ name }: { name: (typeof USER_LOGOS)[number] }) {
  if (name === "Vercel") return <svg viewBox="0 0 150 36" role="img" aria-label={name}><path d="M4 29 18 5l14 24Z" /><text x="40" y="27">VERCEL</text></svg>
  if (name === "Cursor") return <svg viewBox="0 0 150 36" role="img" aria-label={name}><path d="m4 11 14-8 14 8v16l-14 8-14-8Zm3 1.8 10 5.8v11.6l12-20.8H7Z" fillRule="evenodd" /><text x="42" y="27">CURSOR</text></svg>
  if (name === "Oscar") return <svg viewBox="0 0 130 36" role="img" aria-label={name}><text className="user-logo-soft" x="3" y="28">oscar</text></svg>
  if (name === "OpenAI") return <svg viewBox="0 0 150 36" role="img" aria-label={name}><path className="user-logo-knot" d="M18 4a8 8 0 0 1 7 12 8 8 0 0 1-2 15 8 8 0 0 1-14-2 8 8 0 0 1-3-15A8 8 0 0 1 18 4Zm-6 9 6-4 6 4v8l-6 4-6-4Zm0 0 12 8M24 13 12 21M18 9v16" /><text x="42" y="27">OpenAI</text></svg>
  if (name === "Coinbase") return <svg viewBox="0 0 165 36" role="img" aria-label={name}><path d="M19 4a14 14 0 1 0 11 23l-5-4a8 8 0 1 1 0-10l5-4A14 14 0 0 0 19 4Z" /><text x="42" y="27">coinbase</text></svg>
  if (name === "Cash App") return <svg viewBox="0 0 165 36" role="img" aria-label={name}><rect x="2" y="2" width="32" height="32" rx="8" /><path className="user-logo-cut" d="M24 10c-2-2-10-2-10 2 0 5 11 2 11 8 0 5-9 6-13 2m7-15-2 22" /><text x="44" y="27">Cash App</text></svg>
  if (name === "Boom") return <svg viewBox="0 0 155 36" role="img" aria-label={name}><path d="m18 2 3 11 9-7-6 10 12 2-12 2 6 10-9-7-3 11-3-11-9 7 6-10-12-2 12-2L6 6l9 7Z" /><text x="43" y="27">BOOM</text></svg>
  return <svg viewBox="0 0 120 36" role="img" aria-label={name}><text className="user-logo-soft" x="3" y="28">ramp</text></svg>
}

function LogoTrack({ hidden = false }: { hidden?: boolean }) {
  return <div className="user-logo-track" aria-hidden={hidden || undefined}>
    {USER_LOGOS.map((name) => <span key={name}><UserLogo name={name} /></span>)}
  </div>
}

export function UserLogoStrip() {
  return <section className="user-logo-section" aria-labelledby="user-logo-title">
    <h2 id="user-logo-title">Used by teams building the next generation of agents</h2>
    <div className="user-logo-marquee">
      <LogoTrack />
      <LogoTrack hidden />
    </div>
  </section>
}
