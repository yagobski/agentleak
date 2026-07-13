import React from "react"
import ReactDOM from "react-dom/client"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
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
import { Documentation } from "./pages/Documentation"
import { Landing } from "./pages/Landing"
import { Login } from "./pages/Login"
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
        <Route path="/docs" element={<Documentation />} />
        <Route path="/docs/developers" element={<Documentation audience="developers" />} />
        <Route path="/docs/agents" element={<Documentation audience="agents" />} />
        <Route path="/docs/api" element={<Documentation audience="api" />} />
        <Route path="/login" element={<Login initialMode="login" />} />
        <Route path="/register" element={<Login initialMode="register" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="docs" element={<Documentation />} />
      <Route path="docs/developers" element={<Documentation audience="developers" />} />
      <Route path="docs/agents" element={<Documentation audience="agents" />} />
      <Route path="docs/api" element={<Documentation audience="api" />} />
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
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
      <Toaster />
    </TooltipProvider>
  </React.StrictMode>
)
