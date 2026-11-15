// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

export interface Crumb {
  label: string
  to?: string
}

const CrumbContext = createContext<{ crumbs: Crumb[]; set: (c: Crumb[]) => void }>({
  crumbs: [],
  set: () => {},
})

export function CrumbProvider({ children }: { children: ReactNode }) {
  const [crumbs, set] = useState<Crumb[]>([])
  return <CrumbContext.Provider value={{ crumbs, set }}>{children}</CrumbContext.Provider>
}

export function useCrumbState() {
  return useContext(CrumbContext).crumbs
}

/**
 * Declare the page's breadcrumb trail. The last crumb also becomes the browser
 * tab title, so every page gets a distinct title for free.
 */
export function useCrumbs(crumbs: Crumb[]) {
  const { set } = useContext(CrumbContext)
  const key = JSON.stringify(crumbs)
  useEffect(() => {
    const parsed = JSON.parse(key) as Crumb[]
    set(parsed)
    const last = parsed[parsed.length - 1]
    document.title = last ? `${last.label} · AgentLeak` : "AgentLeak"
  }, [key, set])
}
