import { useState } from "react"
import { Loader2, ScanLine, ShieldCheck } from "lucide-react"
import { toast } from "sonner"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function Login() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<"login" | "register">("login")
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
      // The AuthProvider now holds a user; the router renders the app.
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Something went wrong. Please try again."
      toast.error(msg)
    } finally {
      setBusy(false)
    }
  }

  const isRegister = mode === "register"

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex aspect-square size-11 items-center justify-center rounded-xl bg-primary/15 text-primary">
            <ScanLine className="size-5" />
          </div>
          <h1 className="text-xl font-semibold">
            Agent<span className="text-primary">Leak</span>
          </h1>
          <p className="text-sm text-muted-foreground">
            {isRegister ? "Create an account to manage your projects." : "Sign in to your workspace."}
          </p>
        </div>

        <Card className="p-6">
          <form className="space-y-4" onSubmit={submit}>
            {isRegister && (
              <div className="space-y-1.5">
                <Label htmlFor="name" className="text-xs">
                  Name (optional)
                </Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" autoComplete="name" />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs">
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
              <Label htmlFor="password" className="text-xs">
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
            <button
              type="button"
              className="font-medium text-primary hover:underline"
              onClick={() => setMode(isRegister ? "login" : "register")}
            >
              {isRegister ? "Sign in" : "Create one"}
            </button>
          </p>
        </Card>

        <p className="mt-4 flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground">
          <ShieldCheck className="size-3.5 text-sev-ok" /> Accounts &amp; data stay 100% local on this machine.
        </p>
      </div>
    </div>
  )
}
