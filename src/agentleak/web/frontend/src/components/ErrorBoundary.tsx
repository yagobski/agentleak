// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { Component, type ErrorInfo, type ReactNode } from "react"

/** Contains a render error to the page that threw, with something the user can act on. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Kept for the developer console; nothing is sent anywhere.
    console.error("AgentLeak page error", error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <div role="alert" className="max-w-2xl rounded-lg border border-border p-5">
        <h1 className="text-base font-medium">This page failed to render</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The rest of the workspace still works. Reload to retry; if it fails again, the report or response below is
          probably in a shape this version of the interface does not expect.
        </p>
        <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded border border-border bg-muted/50 p-3 font-mono text-[12px]">
          {error.message}
        </pre>
        <div className="mt-3 flex gap-2 text-sm">
          <button type="button" className="rounded border border-border px-3 py-1.5 hover:bg-muted" onClick={() => window.location.reload()}>
            Reload
          </button>
          <a className="rounded px-3 py-1.5 hover:bg-muted" href="/app/">
            Go to dashboard
          </a>
        </div>
      </div>
    )
  }
}
