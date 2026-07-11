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
    <div className="grid min-h-screen bg-[#f2f2ef] text-[#101010] lg:grid-cols-[1fr_480px]">
      <div className="relative hidden overflow-hidden border-r border-black/10 p-10 lg:flex lg:flex-col lg:justify-between">
        <Link to="/" className="font-mono text-sm font-semibold tracking-[-0.04em]">AgentLeak/</Link>
        <p className="relative z-10 max-w-3xl text-6xl font-medium leading-[.92] tracking-[-0.065em]">The answer looked safe. The trace told a different story.</p>
        <div className="font-mono text-[10px] uppercase tracking-[.16em] text-black/40">Local account · http-only session · SQLite</div>
        <div className="auth-orbit" aria-hidden="true" />
      </div>

      <div className="flex items-center justify-center px-5 py-12">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-16 block font-mono text-sm font-semibold tracking-[-0.04em] lg:hidden">AgentLeak/</Link>
          <div className="mb-8">
            <p className="font-mono text-[10px] uppercase tracking-[.16em] text-black/40">{isRegister ? "New local workspace" : "Existing workspace"}</p>
            <h1 className="mt-3 text-4xl font-medium tracking-[-0.055em]">{isRegister ? "Create your account" : "Welcome back"}</h1>
            <p className="mt-3 text-sm leading-6 text-black/50">{isRegister ? "Your account and audit data stay on this AgentLeak instance." : "Sign in to continue auditing your agents."}</p>
          </div>

        <Card className="rounded-none border-black/15 bg-white/70 p-6 text-black shadow-none">
          <form className="space-y-4" onSubmit={submit}>
            {isRegister && (
              <div className="space-y-1.5">
                <Label htmlFor="name" className="text-xs">
                  Name (optional)
                </Label>
                <Input className="border-black/15 bg-white text-black placeholder:text-black/30" id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" autoComplete="name" />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs">
                Email
              </Label>
              <Input
                className="border-black/15 bg-white text-black placeholder:text-black/30"
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
              <Label htmlFor="password" className="text-xs">
                Password
              </Label>
              <Input
                className="border-black/15 bg-white text-black placeholder:text-black/30"
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
            <Button type="submit" className="w-full rounded-none bg-black text-white hover:bg-black/85" disabled={busy}>
              {busy && <Loader2 className="animate-spin" />}
              {isRegister ? "Create account" : "Sign in"}
            </Button>
          </form>

          <p className="mt-4 text-center text-xs text-black/50">
            {isRegister ? "Already have an account?" : "No account yet?"}{" "}
            <Link className="font-medium text-black underline underline-offset-4" to={isRegister ? "/login" : "/register"}>
              {isRegister ? "Sign in" : "Create one"}
            </Link>
          </p>
        </Card>

        <p className="mt-5 text-center font-mono text-[9px] uppercase tracking-[.12em] text-black/40">Password hashed · session cookie http-only · no client-side token</p>
        </div>
      </div>
    </div>
  )
}
