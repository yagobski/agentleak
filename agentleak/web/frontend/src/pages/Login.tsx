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
    <div className="grid min-h-screen bg-[#080909] text-[#f1f1ed] lg:grid-cols-[1fr_480px]">
      <div className="auth-visual relative hidden overflow-hidden border-r border-white/15 p-10 lg:flex lg:flex-col lg:justify-between">
        <Link to="/" className="font-mono text-sm font-medium tracking-[-0.04em]">AgentLeak/</Link>
        <div className="relative z-10"><p className="mb-6 font-mono text-[9px] uppercase tracking-[.14em] text-white/35">PRIVATE WORKSPACE // LOCAL FIRST</p><p className="max-w-3xl text-6xl font-medium leading-[.88] tracking-[-0.07em]">The answer looked safe.<br /><span className="text-white/35">The trace did not.</span></p></div>
        <div className="relative z-10 font-mono text-[9px] uppercase tracking-[.14em] text-white/30">HTTP-ONLY SESSION // SQLITE // NO CLIENT TOKEN</div>
        <div className="auth-signal" aria-hidden="true"><span /><span /><span /></div>
      </div>

      <div className="flex items-center justify-center border-white/15 bg-[#0c0d0d] px-5 py-12">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-16 block font-mono text-sm font-medium tracking-[-0.04em] lg:hidden">AgentLeak/</Link>
          <div className="mb-8">
            <p className="font-mono text-[9px] uppercase tracking-[.14em] text-white/35">{isRegister ? "NEW LOCAL WORKSPACE // 01" : "EXISTING WORKSPACE // 01"}</p>
            <h1 className="mt-3 text-4xl font-medium tracking-[-0.055em]">{isRegister ? "Create your account" : "Welcome back"}</h1>
            <p className="mt-3 text-sm leading-6 text-white/45">{isRegister ? "Your account and audit data stay on this AgentLeak instance." : "Sign in to continue auditing your agents."}</p>
          </div>

        <Card className="rounded-none border-white/15 bg-transparent p-6 text-white shadow-none">
          <form className="space-y-4" onSubmit={submit}>
            {isRegister && (
              <div className="space-y-1.5">
                <Label htmlFor="name" className="font-mono text-[9px] uppercase tracking-wider text-white/55">
                  Name (optional)
                </Label>
                <Input className="rounded-none border-white/15 bg-white/[.03] text-white placeholder:text-white/20 focus-visible:ring-white/50" id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" autoComplete="name" />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="font-mono text-[9px] uppercase tracking-wider text-white/55">
                Email
              </Label>
              <Input
                className="rounded-none border-white/15 bg-white/[.03] text-white placeholder:text-white/20 focus-visible:ring-white/50"
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
              <Label htmlFor="password" className="font-mono text-[9px] uppercase tracking-wider text-white/55">
                Password
              </Label>
              <Input
                className="rounded-none border-white/15 bg-white/[.03] text-white placeholder:text-white/20 focus-visible:ring-white/50"
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
            <Button type="submit" className="w-full rounded-none bg-[#f1f1ed] text-black hover:bg-white/80" disabled={busy}>
              {busy && <Loader2 className="animate-spin" />}
              {isRegister ? "Create account" : "Sign in"}
            </Button>
          </form>

          <p className="mt-4 text-center text-xs text-white/40">
            {isRegister ? "Already have an account?" : "No account yet?"}{" "}
            <Link className="font-medium text-white underline underline-offset-4" to={isRegister ? "/login" : "/register"}>
              {isRegister ? "Sign in" : "Create one"}
            </Link>
          </p>
        </Card>

        <p className="mt-5 text-center font-mono text-[8px] uppercase tracking-[.12em] text-white/25">Password hashed // session cookie http-only // no client-side token</p>
        </div>
      </div>
    </div>
  )
}
