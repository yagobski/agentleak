// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react"
import type { AgentType } from "./api"
import { loadMeta } from "./meta"

// Agent frameworks come from the backend registry (/api/meta), so a newly
// registered framework shows up in the pickers automatically.
export function useAgentTypes(): AgentType[] {
  const [types, setTypes] = useState<AgentType[]>([])
  useEffect(() => {
    loadMeta().then((m) => setTypes(m.agent_types)).catch(() => {})
  }, [])
  return types
}
