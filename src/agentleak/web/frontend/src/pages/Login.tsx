// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Eye, EyeOff, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Brand, ThemeSwitch, usePageMeta } from "@/features/SiteChrome"

// The AgentLeak mark, rasterised from the logo's own outline so the shield
// closes to its point instead of stopping short. The three cuts are the three
// internal channels the audit reads, which is what the caption underneath
// names. 48 columns by 32 rows: the ratio that keeps it square in a monospace
// cell, which is 0.6em wide and 1em tall.
const SHIELD = [
  "                       :#@#:",
  "                    :#@@@@@@@#:",
  "                :=@@@@@@@@@@@@@@#=.",
  "           .:=@@@@@@@@@@@@@@@@@@@@@@#=:.",
  "      .:=#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@#=:.",
  "   :@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@:",
  "   #@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@=",
  "   @@@@@@@@@@@@@@@@@@@@@#=@@@@@@@@@@@@@@@@@@@@@@",
  "  .@@@@@@@@@@@@@@@@@@@=.=@@@@@@@@@@@@@@@@@@@@@@@",
  "  .@@@@@@@@@@@@@@@@=. =@@@@@@@@@@@@@#:@@@@@@@@@@",
  "  .@@@@@@@@@@@@#:. .=@@@@@@@@@@@@@#.:@@@@@@@@@@@",
  "   @@@@@@@@#=.   .#@@@@@@@@@@@@@=  #@@@@@@@@@@@@",
  "    ::::.     .=@@@@@@@@@@@@@@:  :@@@@@@@@@@@@@@",
  "           .=@@@@@@@@@@@@@@#.  .#@@@@@@@@@@@@@@#",
  "       .:#@@@@@@@@@@@@@@@=   .#@@@@@@@@@@@@@@@@=",
  "..::=#@@@@@@@@@@@@@@@@=.   .#@@@@@@@@@@@@@@@@@@.",
  " =@@@@@@@@@@@@@@@@@=.    .#@@@@@@@@@@@@@@@@@@@@",
  "   =@@@@@@@@@@@@=.     :@@@@@@@@@@@@@@@@@@@@@@=",
  "    :@@@@@@@#:.     :#@@@@@@@@@@@@#@@@@@@@@@@@",
  "     .===:.      .=@@@@@@@@@@@@@#.#@@@@@@@@@@=",
  "              .=@@@@@@@@@@@@@@=. #@@@@@@@@@@@",
  "          .:#@@@@@@@@@@@@@@@:  .@@@@@@@@@@@@:",
  "    .::=#@@@@@@@@@@@@@@@@=.   =@@@@@@@@@@@@=",
  "     :#@@@@@@@@@@@@@@@#:    =@@@@@@@@@@@@@#",
  "        =@@@@@@@@@@=:    .=@@@@@@@@@@@@@@#",
  "          :###==:.     :#@@@@@@@@@@@@@@@#",
  "                    .=@@@@@@@@@@@@@@@@@:",
  "                 :=@@@@@@@@@@@@@@@@@@#.",
  "            :=#@@@@@@@@@@@@@@@@@@@@@:",
  "             ::#@@@@@@@@@@@@@@@@@@:",
  "                 .=#@@@@@@@@@@@=.",
  "                     :=#@@@#:.",
]

export function Login({ initialMode = "login" }: { initialMode?: "login" | "register" }) {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  // React Router reuses this component when switching between /register and
  // /login. Derive the mode from the route prop so both links update the form
  // immediately instead of retaining the first mounted page's state.
  const mode = initialMode
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      if (mode === "register") await register(email, password, name)
      else await login(email, password)
      navigate("/")
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Something went wrong. Please try again."
      toast.error(msg)
    } finally {
      setBusy(false)
    }
  }

  const isRegister = mode === "register"
  usePageMeta(
    isRegister ? "Create an AgentLeak account" : "Sign in to AgentLeak",
    isRegister ? "Create your AgentLeak workspace for private, local-first AI agent audits." : "Sign in to your AgentLeak workspace and continue testing AI agent privacy.",
    { noIndex: true },
  )

  return (
    <div className="auth-shell">
      <nav className="auth-nav">
        <Brand />
        <div className="auth-nav-links">
          <Link to="/docs">Docs</Link>
          <a href="/openapi.json">API</a>
          <ThemeSwitch />
          <Link className="auth-nav-cta" to={isRegister ? "/login" : "/register"}>
            {isRegister ? "Sign in" : "Create account"}
          </Link>
        </div>
      </nav>

      <main className="auth-stage">
        <section className="auth-mark">
          <pre className="auth-ascii" aria-hidden="true">
            {SHIELD.map((line, i) => (
              <span key={i} style={{ "--row": i } as React.CSSProperties}>{line}</span>
            ))}
          </pre>
          <p className="auth-mark-caption">
            <span>tool calls</span>
            <span>shared memory</span>
            <span>logs</span>
          </p>
        </section>

        <section className="auth-form-panel" aria-labelledby="auth-title">
          <div className="auth-form-inner">
            <h1 className="auth-col-label" id="auth-title">
              {isRegister ? "Create your account" : "Sign in with email"}
            </h1>

            <form className="auth-form" onSubmit={submit}>
              {isRegister && (
                <div className="auth-field">
                  <Label htmlFor="name">Name</Label>
                  <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" autoComplete="name" />
                </div>
              )}
              <div className="auth-field">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                />
              </div>
              <div className="auth-field">
                <Label htmlFor="password">Password</Label>
                <div className="auth-password">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={isRegister ? 8 : undefined}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={isRegister ? "At least 8 characters" : "Password"}
                    autoComplete={isRegister ? "new-password" : "current-password"}
                  />
                  <button
                    type="button"
                    className="auth-reveal"
                    onClick={() => setShowPassword((value) => !value)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff /> : <Eye />}
                  </button>
                </div>
              </div>
              <Button type="submit" className="auth-submit" disabled={busy}>
                {busy && <Loader2 className="animate-spin" />}
                {isRegister ? "Create account" : "Sign in"}
              </Button>
            </form>

            <p className="auth-switch">
              {isRegister ? "Already have an account?" : "No account yet?"}{" "}
              <Link to={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Create one"}</Link>
            </p>

            <p className="auth-agent-note">
              Building an agent? It signs in through the{" "}
              <Link to="/docs/agents">machine API</Link>, no browser session needed.
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}
