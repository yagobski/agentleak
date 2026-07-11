import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function Login({ initialMode = "login" }: { initialMode?: "login" | "register" }) {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [mode] = useState<"login" | "register">(initialMode)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
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

  return (
    <div className="platform-auth grid min-h-screen lg:grid-cols-[1fr_480px]">
      <div className="platform-auth-visual relative hidden overflow-hidden p-10 lg:flex lg:flex-col lg:justify-between">
        <Link to="/" className="cursor-brand"><span className="cursor-brand-mark" aria-hidden="true"><i /><i /><i /></span><span>AGENTLEAK</span></Link>
        <div className="platform-auth-story">
          <p>Private workspace / local first</p>
          <h2>The answer looked safe.<br /><span>The trace did not.</span></h2>
          <div className="platform-auth-preview">
            <header><span>support-router / run_2048</span><b>Analysis complete</b></header>
            <div><i>01</i><span><b>tool_response</b><small>Customer record received</small></span><em>source</em></div>
            <div data-leak="true"><i>02</i><span><b>tool_call</b><small>Email forwarded to calendar</small></span><em>exposed</em></div>
            <div data-leak="true"><i>03</i><span><b>shared_memory</b><small>Account ID copied to memory</small></span><em>exposed</em></div>
          </div>
        </div>
        <div className="platform-auth-meta">HTTP-only session / SQLite / no client token</div>
      </div>

      <div className="platform-auth-panel flex items-center justify-center px-5 py-12">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-16 block text-sm font-semibold lg:hidden">AGENTLEAK</Link>
          <div className="mb-8">
            <p className="text-xs text-muted-foreground">{isRegister ? "New workspace" : "Existing workspace"}</p>
            <h1 className="mt-3 text-[34px] font-normal tracking-[-0.04em]">{isRegister ? "Create your account" : "Welcome back"}</h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">{isRegister ? "Your account and audit data stay on this AgentLeak instance." : "Sign in to continue auditing your agents."}</p>
          </div>

        <Card className="platform-auth-card p-6">
          <form className="space-y-4" onSubmit={submit}>
            {isRegister && (
              <div className="space-y-1.5">
                <Label htmlFor="name" className="text-xs text-muted-foreground">
                  Name (optional)
                </Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" autoComplete="name" />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs text-muted-foreground">
                Email
              </Label>
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
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-xs text-muted-foreground">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                required
                minLength={isRegister ? 8 : undefined}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isRegister ? "At least 8 characters" : "••••••••"}
                autoComplete={isRegister ? "new-password" : "current-password"}
              />
            </div>
            <Button type="submit" className="w-full" disabled={busy}>
              {busy && <Loader2 className="animate-spin" />}
              {isRegister ? "Create account" : "Sign in"}
            </Button>
          </form>

          <p className="mt-4 text-center text-xs text-muted-foreground">
            {isRegister ? "Already have an account?" : "No account yet?"}{" "}
            <Link className="font-medium text-foreground underline underline-offset-4" to={isRegister ? "/login" : "/register"}>
              {isRegister ? "Sign in" : "Create one"}
            </Link>
          </p>
        </Card>

        <p className="mt-5 text-center text-[10px] text-muted-foreground">Password hashed / HTTP-only session / no client-side token</p>
        </div>
      </div>
    </div>
  )
}
