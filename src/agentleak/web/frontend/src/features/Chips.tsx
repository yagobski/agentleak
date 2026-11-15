// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useState } from "react"
import { Check, Link2 } from "lucide-react"
import { toast } from "sonner"
import type { Badge, Detection, Report } from "@/lib/api"
import { badgeChipClass, verdictColor } from "@/lib/format"
import { cn } from "@/lib/utils"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

const LEVEL_BADGE: Record<number, Badge> = { 4: "critical", 3: "high", 2: "medium", 1: "low" }

/** Severity level chip. The label (L1-L4) always carries the meaning; color only reinforces it. */
export function LevelChip({ level, className }: { level: number; className?: string }) {
  const badge = LEVEL_BADGE[level] ?? "low"
  return (
    <span className={cn("inline-flex rounded px-1.5 py-0.5 font-mono text-[11px] font-semibold leading-none", badgeChipClass(badge), className)}>
      L{level}
    </span>
  )
}

/** Verdict as returned by the engine, text first; a dot reinforces the color. */
export function VerdictLabel({ verdict, className }: { verdict: Report["verdict"]; className?: string }) {
  const color = verdictColor(verdict)
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] font-medium", className)} style={{ color }}>
      <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      {verdict}
    </span>
  )
}

/**
 * Which detector tiers ran, and whether detection was degraded. Shown on every
 * result: a clean result from the fast (pattern-only) tier is a weaker claim
 * than one from a hybrid run, and the reader has to be able to see that.
 */
export function DetectionBadge({ detection, className }: { detection?: Detection; className?: string }) {
  if (!detection) {
    return (
      <span className={cn("inline-flex items-center gap-1.5 rounded border border-border px-2 py-0.5 text-[11px] text-muted-foreground", className)}>
        detection tier not recorded
      </span>
    )
  }
  const tiers = detection.tiers.length ? detection.tiers.join(" + ") : "none"
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className={cn(
            "inline-flex items-center gap-1.5 whitespace-nowrap rounded border px-2 py-0.5 font-mono text-[11px]",
            detection.degraded ? "border-sev-l2/50 text-sev-l2" : "border-border text-muted-foreground",
            className,
          )}
        >
          <span className="font-sans font-medium text-foreground">{detection.mode}</span>
          <span>{tiers}</span>
          <span className="font-sans">{detection.degraded ? "· degraded" : "· complete"}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-xs">
        Detection mode <b>{detection.mode}</b>; tiers that ran: {tiers}.{" "}
        {detection.degraded
          ? "A requested tier did not run, so this result is weaker than the mode implies."
          : "Every requested tier ran."}{" "}
        Detectors are deterministic patterns and dictionaries; data they do not recognise is not reported.
      </TooltipContent>
    </Tooltip>
  )
}

export function CopyLinkButton({ path, label = "Copy link", className }: { path: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false)
  function copy() {
    const url = new URL(`/app${path}`, window.location.origin).toString()
    navigator.clipboard
      .writeText(url)
      .then(() => {
        setDone(true)
        toast.success("Link copied")
        window.setTimeout(() => setDone(false), 1500)
      })
      .catch(() => toast.error("Clipboard unavailable"))
  }
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        copy()
      }}
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      aria-label={label}
      title={label}
    >
      {done ? <Check className="size-3.5" /> : <Link2 className="size-3.5" />}
      <span className="sr-only sm:not-sr-only">{label}</span>
    </button>
  )
}
