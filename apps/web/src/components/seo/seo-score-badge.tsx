"use client"
import { cn } from "@/lib/utils"

interface SeoScoreBadgeProps {
  score: number
  className?: string
}

export function SeoScoreBadge({ score, className }: SeoScoreBadgeProps) {
  const variant =
    score >= 80 ? "good" : score >= 50 ? "warn" : "poor"

  const styles = {
    good: "bg-emerald-500/10 text-emerald-700 border-emerald-500/20",
    warn: "bg-amber-500/10 text-amber-700 border-amber-500/20",
    poor: "bg-rose-500/10 text-rose-700 border-rose-500/20",
  }

  const labels = {
    good: "Good",
    warn: "Needs work",
    poor: "Poor",
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        styles[variant],
        className
      )}
    >
      {score}
      <span className="opacity-70">· {labels[variant]}</span>
    </span>
  )
}
