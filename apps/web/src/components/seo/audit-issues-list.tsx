"use client"
import { CheckCircle2, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface AuditIssuesListProps {
  issues: string[]
  className?: string
}

export function AuditIssuesList({ issues, className }: AuditIssuesListProps) {
  if (issues.length === 0) {
    return (
      <div className={cn("flex items-center gap-2 text-sm text-emerald-600", className)}>
        <CheckCircle2 size={16} />
        All SEO checks passed
      </div>
    )
  }

  return (
    <ul className={cn("space-y-1.5", className)}>
      {issues.map((issue) => (
        <li key={issue} className="flex items-start gap-2 text-sm text-muted-foreground">
          <XCircle size={14} className="mt-0.5 shrink-0 text-rose-500" />
          {issue}
        </li>
      ))}
    </ul>
  )
}
