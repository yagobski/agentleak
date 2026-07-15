import { useEffect, useState } from "react"
import { ExternalLink, Github, KeyRound, Loader2, Save, ShieldCheck, Trash2, UserRound } from "lucide-react"
import { toast } from "sonner"
import { api, type Meta } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { PageHeader } from "@/layout/AppShell"

export function Settings() {
  const [meta, setMeta] = useState<Meta | null>(null)
  useEffect(() => {
    api.meta().then(setMeta).catch(() => {})
  }, [])

  return (
    <div className="animate-fade-up max-w-2xl space-y-4">
      <PageHeader title="Settings" description="Your account and this AgentLeak instance." />

      <AccountCard />
      <PasswordCard />
      <DangerZoneCard />

      <Card className="p-5">
        <div className="flex items-center gap-2 text-sm font-medium">
          <ShieldCheck className="size-4 text-sev-ok" /> Local & private
        </div>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Everything runs on this machine. Traces are analyzed in-process and stored in a local SQLite
          database under <code className="rounded bg-muted px-1.5 py-0.5 text-xs">$AGENTLEAK_HOME</code>{" "}
          (default <code className="rounded bg-muted px-1.5 py-0.5 text-xs">~/.agentleak</code>). No data
          leaves your machine.
        </p>

        <Separator className="my-4" />

        <dl className="grid grid-cols-2 gap-y-2.5 text-sm">
          <dt className="text-muted-foreground">Version</dt>
          <dd className="font-mono">{meta?.version ?? "—"}</dd>
          <dt className="text-muted-foreground">Scoring</dt>
          <dd>AgentRisk (RI = WSL / ρ_S)</dd>
          <dt className="text-muted-foreground">Detectors</dt>
          <dd className="font-mono text-xs">{meta?.detectors.join(", ")}</dd>
          <dt className="text-muted-foreground">Channels</dt>
          <dd className="font-mono text-xs">{meta?.channels.length} normalized</dd>
        </dl>

        <Separator className="my-4" />

        <div className="flex flex-wrap gap-4 text-sm">
          <a
            href="https://github.com/yagobski/agentleak-oss"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-primary hover:underline"
          >
            <Github className="size-4" /> Source
          </a>
          <a
            href="https://arxiv.org/abs/2602.11510"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-primary hover:underline"
          >
            <ExternalLink className="size-4" /> AgentRisk paper
          </a>
        </div>
      </Card>
    </div>
  )
}

// ------------------------------------------------------------- Account
function AccountCard() {
  const { user, setUser } = useAuth()
  const [name, setName] = useState(user?.name ?? "")
  const [busy, setBusy] = useState(false)

  useEffect(() => setName(user?.name ?? ""), [user?.name])

  async function save() {
    if (!name.trim()) return toast.error("Name cannot be empty.")
    setBusy(true)
    try {
      setUser(await api.updateMe({ name: name.trim() }))
      toast.success("Profile updated.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not update profile.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 text-sm font-medium">
        <UserRound className="size-4 text-primary" /> Account
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <Label className="text-xs">Email</Label>
          <Input value={user?.email ?? ""} disabled className="mt-1 opacity-70" />
        </div>
        <div>
          <Label className="text-xs">Display name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
        </div>
      </div>
      {user?.is_admin && (
        <p className="mt-2 text-xs text-muted-foreground">
          You are an administrator of this deployment —{" "}
          <a href="/admin" className="text-primary hover:underline">open the console</a>.
        </p>
      )}
      <Button size="sm" className="mt-3" onClick={save} disabled={busy || name.trim() === (user?.name ?? "")}>
        {busy ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Save className="mr-1.5 size-3.5" />}
        Save
      </Button>
    </Card>
  )
}

// ------------------------------------------------------------ Password
function PasswordCard() {
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [busy, setBusy] = useState(false)

  async function submit() {
    if (next.length < 8) return toast.error("New password must be at least 8 characters.")
    setBusy(true)
    try {
      await api.changePassword({ current_password: current, new_password: next })
      toast.success("Password changed — please sign in again.")
      window.location.href = "/"
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not change password.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 text-sm font-medium">
        <KeyRound className="size-4 text-primary" /> Password
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <Label className="text-xs">Current password</Label>
          <Input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">New password</Label>
          <Input type="password" value={next} onChange={(e) => setNext(e.target.value)} className="mt-1" />
        </div>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Changing your password signs you out everywhere — you'll need to sign in again.
      </p>
      <Button size="sm" className="mt-3" onClick={submit} disabled={busy || !current || !next}>
        {busy ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <KeyRound className="mr-1.5 size-3.5" />}
        Change password
      </Button>
    </Card>
  )
}

// --------------------------------------------------------- Danger zone
function DangerZoneCard() {
  const { user } = useAuth()
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)

  async function remove() {
    if (!window.confirm("Delete your account and ALL your projects/runs? This cannot be undone.")) return
    setBusy(true)
    try {
      await api.deleteAccount({ password })
      window.location.href = "/"
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not delete account.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="border-sev-l4/30 p-5">
      <div className="flex items-center gap-2 text-sm font-medium text-sev-l4">
        <Trash2 className="size-4" /> Danger zone
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Permanently delete your account and every project, run, and code scan it owns.
        {user?.is_admin && " The last admin of a deployment cannot delete their own account."}
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <div className="min-w-56">
          <Label className="text-xs">Confirm with your password</Label>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1" />
        </div>
        <Button variant="destructive" size="sm" onClick={remove} disabled={busy || !password}>
          {busy ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Trash2 className="mr-1.5 size-3.5" />}
          Delete my account
        </Button>
      </div>
    </Card>
  )
}

