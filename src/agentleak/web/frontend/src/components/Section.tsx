// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useId, type ReactNode } from "react"
import { cn } from "@/lib/utils"

/** A titled, bordered block: the container every rebuilt page uses. */
export function Section({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  const id = useId()
  return (
    <section aria-labelledby={id} className={cn("min-w-0 rounded-lg border border-border bg-card", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <div className="min-w-0">
          <h2 id={id} className="text-sm font-medium">
            {title}
          </h2>
          {description && <p className="mt-0.5 max-w-3xl text-[12px] text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      <div className={cn("min-w-0", bodyClassName)}>{children}</div>
    </section>
  )
}

/** One labelled setting: label and help on the left, the control on the right. */
export function FieldRow({
  label,
  htmlFor,
  help,
  children,
}: {
  label: ReactNode
  htmlFor?: string
  help?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="grid gap-x-6 gap-y-1.5 border-b border-border/70 px-4 py-3 last:border-b-0 sm:grid-cols-[14rem_minmax(0,1fr)]">
      <div className="min-w-0">
        {htmlFor ? (
          <label htmlFor={htmlFor} className="text-[13px] font-medium">
            {label}
          </label>
        ) : (
          <span className="text-[13px] font-medium">{label}</span>
        )}
        {help && <p className="mt-0.5 text-[12px] text-muted-foreground">{help}</p>}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

/** A number with its label and, where it is a rate or a mean, its denominator. */
export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="min-w-0 py-1">
      <dt className="text-[12px] text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-mono text-2xl leading-none tnum">{value}</dd>
      {note && <dd className="mt-1 text-[11px] text-muted-foreground">{note}</dd>}
    </div>
  )
}

export const inputSm = "h-8 rounded-md border border-input bg-background px-2 text-[13px]"
