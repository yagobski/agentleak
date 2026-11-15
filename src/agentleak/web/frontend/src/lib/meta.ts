// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react"
import { api, type Meta } from "./api"

// /api/meta is static for the life of the server process: fetch it once and
// share the promise, instead of every page re-requesting it.
let pending: Promise<Meta> | null = null

export function loadMeta(): Promise<Meta> {
  if (!pending) {
    pending = api.meta().catch((error) => {
      pending = null
      throw error
    })
  }
  return pending
}

export function useMeta(): Meta | null {
  const [meta, setMeta] = useState<Meta | null>(null)
  useEffect(() => {
    let live = true
    loadMeta().then((m) => live && setMeta(m)).catch(() => {})
    return () => {
      live = false
    }
  }, [])
  return meta
}

// Fallbacks for a server older than the source/emission split in /api/meta.
// They mirror agentrisk.BASELINE_CHANNELS; the live value always wins.
const FALLBACK_CHANNELS = [
  "user_input",
  "final_output",
  "inter_agent_message",
  "shared_memory",
  "tool_call",
  "tool_response",
  "log",
  "generated_file",
]
const FALLBACK_SOURCES = ["user_input", "tool_response"]

export interface ChannelSplit {
  all: string[]
  sources: string[]
  emissions: string[]
  isSource: (channel: string) => boolean
}

export function channelSplit(meta: Meta | null): ChannelSplit {
  const all = meta?.channels?.length ? meta.channels : FALLBACK_CHANNELS
  const sources = meta?.source_channels ?? FALLBACK_SOURCES
  const emissions = meta?.emission_channels ?? all.filter((c) => !sources.includes(c))
  const set = new Set(sources)
  return { all, sources, emissions, isSource: (c) => set.has(c) }
}
