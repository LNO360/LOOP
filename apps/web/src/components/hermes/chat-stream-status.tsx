"use client"

import { useEffect, useState, type ReactNode } from "react"
import { cn } from "@/lib/utils"
import type { StreamStatus } from "@/hooks/use-hermes"
import { CheckCircle2, Circle, Loader2, Wrench, PenLine, Radio } from "lucide-react"

function formatElapsed(ms: number) {
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

const PHASE_ICON: Record<StreamStatus["phase"], ReactNode> = {
  idle: <Circle size={12} className="text-muted-foreground" />,
  connecting: <Loader2 size={12} className="animate-spin text-indigo-600" />,
  thinking: <Loader2 size={12} className="animate-spin text-indigo-600" />,
  tool: <Wrench size={12} className="text-amber-600" />,
  writing: <PenLine size={12} className="text-emerald-600" />,
  done: <CheckCircle2 size={12} className="text-emerald-600" />,
  error: <Circle size={12} className="text-red-500" />,
}

interface StreamStatusBarProps {
  status: StreamStatus | null
  className?: string
}

/** Live status above the composer while Hermes is working. */
export function StreamStatusBar({ status, className }: StreamStatusBarProps) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!status || status.phase === "idle" || status.phase === "done") {
      setElapsed(0)
      return
    }
    const tick = () => setElapsed(Date.now() - status.startedAt)
    tick()
    const id = setInterval(tick, 500)
    return () => clearInterval(id)
  }, [status])

  if (!status || status.phase === "idle") return null

  return (
    <div
      className={cn(
        "rounded-xl border border-indigo-200/80 bg-gradient-to-r from-indigo-50/90 to-white px-3 py-2.5 shadow-sm",
        className
      )}
    >
      <div className="flex items-center gap-2">
        {PHASE_ICON[status.phase]}
        <span className="text-sm font-medium text-foreground">{status.label}</span>
        <span className="ml-auto font-mono text-[11px] text-muted-foreground tabular-nums">
          {formatElapsed(elapsed)}
        </span>
      </div>
      {status.toolCount > 0 && (
        <p className="mt-1 pl-5 text-[11px] text-muted-foreground">
          {status.toolCount} tool{status.toolCount !== 1 ? "s" : ""}
          {status.lastToolName ? ` · last: ${status.lastToolName}` : ""}
        </p>
      )}
    </div>
  )
}

interface ActivityStep {
  label: string
  at: string
}

interface ActivityTimelineProps {
  steps: ActivityStep[]
  isLive?: boolean
  className?: string
}

/** Step-by-step progress inside the assistant message bubble. */
export function ActivityTimeline({ steps, isLive, className }: ActivityTimelineProps) {
  if (steps.length === 0 && !isLive) return null

  return (
    <div
      className={cn(
        "mb-3 rounded-xl border border-border/50 bg-slate-50/80 px-3 py-2.5",
        className
      )}
    >
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        <Radio size={11} className={isLive ? "animate-pulse text-indigo-600" : ""} />
        {isLive ? "In progress" : "Activity"}
      </div>
      <ul className="space-y-1.5">
        {steps.map((step, i) => (
          <li key={`${step.at}-${i}`} className="flex items-start gap-2 text-xs text-foreground/85">
            {i === steps.length - 1 && isLive ? (
              <Loader2 size={12} className="mt-0.5 shrink-0 animate-spin text-indigo-600" />
            ) : (
              <CheckCircle2 size={12} className="mt-0.5 shrink-0 text-emerald-600/80" />
            )}
            <span className="leading-relaxed">{step.label}</span>
          </li>
        ))}
        {isLive && steps.length === 0 && (
          <li className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 size={12} className="animate-spin text-indigo-600" />
            Waiting for Hermes…
          </li>
        )}
      </ul>
    </div>
  )
}
