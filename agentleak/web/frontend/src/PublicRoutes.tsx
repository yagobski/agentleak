import { Navigate, Route, Routes } from "react-router-dom"
import { Documentation, RedTeamPluginDocumentation } from "./pages/Documentation"
import { FeaturePage } from "./pages/FeaturePage"
import { Integrations } from "./pages/Integrations"
import { Landing } from "./pages/Landing"
import { Login } from "./pages/Login"
import { Benchmark } from "./pages/Benchmark"
import { Compare } from "./pages/Compare"
import { Compliance } from "./pages/Compliance"
import { Research } from "./pages/Research"
import { FeaturesHub, SeoPage } from "./pages/SeoPages"

// The logged-out site: marketing, docs and research. Exported on its own so
// the build-time prerender renders exactly what a crawler should receive,
// without going through the auth gate (which would render a spinner).
export function PublicRoutes() {
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
        <Route path="/benchmark" element={<Benchmark />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/compliance/eu-ai-act" element={<Compliance />} />
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
