import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ArrowRight, CheckCircle2, Eye, EyeOff, Loader2, LockKeyhole, Mail, User } from "lucide-react"
import { toast } from "sonner"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Brand, ThemeSwitch, usePageMeta } from "@/features/SiteChrome"

const auditRows = [
  ["01", "tool_response", "Customer record received", "source"],
  ["02", "tool_call", "Forwarded email and address to calendar", "exposed"],
  ["03", "shared_memory", "Account ID persisted for next agent", "exposed"],
  ["04", "final_output", "Clean response to the customer", "clean"],
]

export function Login({ initialMode = "login" }: { initialMode?: "login" | "register" }) {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [mode] = useState<"login" | "register">(initialMode)
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
    <div className="auth-shell min-h-screen">
      <nav className="auth-nav">
        <Brand />
        <div>
          <Link to="/docs">Docs</Link>
          <a href="/openapi.json">API</a>
          <ThemeSwitch />
          <Link to={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Create account"}</Link>
        </div>
      </nav>

      <main className="auth-stage">
        <section className="auth-product">
          <div className="auth-copy">
            <p>Private workspace / local-first audit</p>
            <h1>{isRegister ? "Create the place where agents get tested." : "Return to the audit room."}</h1>
            <span>
              AgentLeak keeps the account simple: a server-side session for humans,
              scoped project keys for agents, and no client-side token storage.
            </span>
          </div>

          <div className="auth-live" aria-label="AgentLeak product preview">
            <div className="auth-platform-window">
              <header>
                <span>support-router</span>
                <b>Analysis complete</b>
              </header>
              <div className="auth-platform-body">
                <aside>
                  <span data-active="true">Trace</span>
                  <span>AgentRisk</span>
                  <span>Policy</span>
                </aside>
                <section>
                  <div className="auth-risk">
                    <small>AgentRisk RI</small>
                    <strong>0.38</strong>
                    <i>
                      <b />
                    </i>
                    <span>2 blocked channels / final answer clean</span>
                  </div>
                  <div className="auth-events">
                    {auditRows.map(([id, channel, detail, status]) => (
                      <div key={id} data-status={status}>
                        <i>{id}</i>
                        <span>
                          <b>{channel}</b>
                          <small>{detail}</small>
                        </span>
                        <em>{status}</em>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </div>
            <div className="auth-terminal-strip">
              <header>
                <span>agent terminal</span>
                <b>project key</b>
              </header>
              <code>
                <span>$ agentleak scan --project support-router</span>
                <span>trace accepted: 41 events</span>
              </code>
            </div>
          </div>
        </section>

        <section className="auth-form-panel" aria-labelledby="auth-title">
          <div className="auth-form-head">
            <p>{isRegister ? "New workspace" : "Existing workspace"}</p>
            <h2 id="auth-title">{isRegister ? "Create your account" : "Sign in"}</h2>
            <span>{isRegister ? "Start with one local account, then create project keys for agents." : "Continue auditing agents, scenarios and project runs."}</span>
          </div>

          <form className="auth-form" onSubmit={submit}>
            {isRegister && (
              <div className="auth-field">
                <Label htmlFor="name">Name</Label>
                <div>
                  <User aria-hidden="true" />
                  <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" autoComplete="name" />
                </div>
              </div>
            )}
            <div className="auth-field">
              <Label htmlFor="email">Email</Label>
              <div>
                <Mail aria-hidden="true" />
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
            </div>
            <div className="auth-field">
              <Label htmlFor="password">Password</Label>
              <div>
                <LockKeyhole aria-hidden="true" />
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
              {busy ? <Loader2 className="animate-spin" /> : <ArrowRight />}
              {isRegister ? "Create account" : "Sign in"}
            </Button>
          </form>

          <div className="auth-assurance">
            <span>
              <CheckCircle2 /> Passwords are hashed server-side
            </span>
            <span>
              <CheckCircle2 /> HTTP-only session cookie
            </span>
            <span>
              <CheckCircle2 /> Project keys stay scoped to one agent
            </span>
          </div>

          <p className="auth-switch">
            {isRegister ? "Already have an account?" : "No account yet?"}{" "}
            <Link to={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Create one"}</Link>
          </p>
        </section>
      </main>
    </div>
  )
}
