import React from "react"
import ReactDOM from "react-dom/client"
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom"
import "@fontsource-variable/hanken-grotesk"
import "@fontsource/jetbrains-mono/400.css"
import "@fontsource/jetbrains-mono/500.css"
import "@fontsource/jetbrains-mono/600.css"
import "./index.css"
import { Loader2 } from "lucide-react"
import { TooltipProvider } from "./components/ui/tooltip"
import { Toaster } from "./components/ui/sonner"
import { AuthProvider, useAuth } from "./lib/auth"
import { AppShell } from "./layout/AppShell"
import { Admin } from "./pages/Admin"
import { Dashboard } from "./pages/Dashboard"
import { Documentation, RedTeamPluginDocumentation } from "./pages/Documentation"
import { FeaturePage } from "./pages/FeaturePage"
import { Landing } from "./pages/Landing"
import { Integrations } from "./pages/Integrations"
import { Login } from "./pages/Login"
import { Research } from "./pages/Research"
import { FeaturesHub, SeoPage } from "./pages/SeoPages"
import { Playground } from "./pages/Playground"
import { ProjectDetail } from "./pages/ProjectDetail"
import { Projects } from "./pages/Projects"
import { RunView } from "./pages/RunView"
import { Scenarios } from "./pages/Scenarios"
import { Settings } from "./pages/Settings"

// Apply the saved theme before first paint. Dark is the default so the
// product matches the marketing site; one-time migration flips accounts the
// old "warm light" migration had pinned to light.
if (!localStorage.getItem("agentleak-dark-ui-v1")) {
  localStorage.setItem("agentleak-theme", "dark")
  localStorage.setItem("agentleak-dark-ui-v1", "1")
}
const savedTheme = localStorage.getItem("agentleak-theme")
document.documentElement.classList.toggle("dark", savedTheme ? savedTheme === "dark" : true)

function ScrollToRoute() {
  const { hash, pathname } = useLocation()
  React.useEffect(() => {
    let frame = 0
    let observer: MutationObserver | undefined
    let timeout = 0
    const scrollToHash = () => {
      const target = document.getElementById(hash.slice(1))
      if (!target) return false
      window.scrollTo({
        top: target.getBoundingClientRect().top + window.scrollY,
        left: 0,
        behavior: "auto",
      })
      return true
    }
    frame = window.requestAnimationFrame(() => {
      if (!hash) {
        window.scrollTo({ top: 0, left: 0, behavior: "auto" })
        return
      }
      if (scrollToHash()) return
      observer = new MutationObserver(() => {
        if (!scrollToHash()) return
        observer?.disconnect()
        window.clearTimeout(timeout)
      })
      observer.observe(document.body, { childList: true, subtree: true })
      timeout = window.setTimeout(() => observer?.disconnect(), 3000)
    })
    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(timeout)
      observer?.disconnect()
    }
  }, [hash, pathname])
  return null
}

function AppRoutes() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    )
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/features" element={<FeaturesHub />} />
        <Route path="/features/:slug" element={<FeaturePage />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/security" element={<SeoPage />} />
        <Route path="/use-cases/multi-agent-privacy" element={<SeoPage />} />
        <Route path="/about" element={<SeoPage />} />
        <Route path="/research" element={<Research />} />
        <Route path="/faq" element={<Navigate to="/#faq" replace />} />
        <Route path="/docs" element={<Documentation />} />
        <Route path="/docs/getting-started" element={<Documentation audience="gettingStarted" />} />
        <Route path="/docs/integrations" element={<Documentation audience="integrations" />} />
        <Route path="/docs/scoring" element={<Documentation audience="scoring" />} />
        <Route path="/docs/developers" element={<Documentation audience="developers" />} />
        <Route path="/docs/agents" element={<Documentation audience="agents" />} />
        <Route path="/docs/api" element={<Documentation audience="api" />} />
        <Route path="/docs/privacy-compliance" element={<Documentation audience="privacyCompliance" />} />
        <Route path="/docs/red-team" element={<Documentation audience="redteam" />} />
        <Route path="/docs/red-team/configuration" element={<Documentation audience="redteamConfiguration" />} />
        <Route path="/docs/red-team/architecture" element={<Documentation audience="redteamArchitecture" />} />
        <Route path="/docs/red-team/vulnerabilities" element={<Documentation audience="redteamVulnerabilities" />} />
        <Route path="/docs/red-team/llm-vulnerability-types" element={<Documentation audience="redteamVulnerabilities" />} />
        <Route path="/docs/red-team/plugins" element={<Documentation audience="redteamPlugins" />} />
        <Route path="/docs/red-team/plugins/:pluginId" element={<RedTeamPluginDocumentation />} />
        <Route path="/docs/red-team/strategies" element={<Documentation audience="redteamStrategies" />} />
        <Route path="/docs/ci-cd" element={<Documentation audience="ciCd" />} />
        <Route path="/login" element={<Login initialMode="login" />} />
        <Route path="/register" element={<Login initialMode="register" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="features/:slug" element={<FeaturePage />} />
      <Route path="integrations" element={<Integrations />} />
      <Route path="features" element={<FeaturesHub />} />
      <Route path="security" element={<SeoPage />} />
      <Route path="use-cases/multi-agent-privacy" element={<SeoPage />} />
      <Route path="about" element={<SeoPage />} />
      <Route path="research" element={<Research />} />
      <Route path="faq" element={<Navigate to="/" replace />} />
      <Route path="docs" element={<Documentation />} />
      <Route path="docs/getting-started" element={<Documentation audience="gettingStarted" />} />
      <Route path="docs/integrations" element={<Documentation audience="integrations" />} />
      <Route path="docs/scoring" element={<Documentation audience="scoring" />} />
      <Route path="docs/developers" element={<Documentation audience="developers" />} />
      <Route path="docs/agents" element={<Documentation audience="agents" />} />
      <Route path="docs/api" element={<Documentation audience="api" />} />
      <Route path="docs/privacy-compliance" element={<Documentation audience="privacyCompliance" />} />
      <Route path="docs/red-team" element={<Documentation audience="redteam" />} />
      <Route path="docs/red-team/configuration" element={<Documentation audience="redteamConfiguration" />} />
      <Route path="docs/red-team/architecture" element={<Documentation audience="redteamArchitecture" />} />
      <Route path="docs/red-team/vulnerabilities" element={<Documentation audience="redteamVulnerabilities" />} />
      <Route path="docs/red-team/llm-vulnerability-types" element={<Documentation audience="redteamVulnerabilities" />} />
      <Route path="docs/red-team/plugins" element={<Documentation audience="redteamPlugins" />} />
      <Route path="docs/red-team/plugins/:pluginId" element={<RedTeamPluginDocumentation />} />
      <Route path="docs/red-team/strategies" element={<Documentation audience="redteamStrategies" />} />
      <Route path="docs/ci-cd" element={<Documentation audience="ciCd" />} />
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:id" element={<ProjectDetail />} />
        <Route path="runs/:id" element={<RunView />} />
        <Route path="playground" element={<Playground />} />
        <Route path="scenarios" element={<Scenarios />} />
        <Route path="settings" element={<Settings />} />
        {user.is_admin && <Route path="admin" element={<Admin />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TooltipProvider delayDuration={200}>
      <BrowserRouter>
        <ScrollToRoute />
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
      <Toaster />
    </TooltipProvider>
  </React.StrictMode>
)
