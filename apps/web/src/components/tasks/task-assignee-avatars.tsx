"use client"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"

/** Resolve display names from API assignee_names or legacy assignee_id. */
export function assigneeNamesForTask(
  task: { assignee_names?: string[]; assignee_id?: string | null },
  memberMap?: Record<string, string>
): string[] {
  if (task.assignee_names?.length) return task.assignee_names
  if (task.assignee_id && memberMap?.[task.assignee_id]) return [memberMap[task.assignee_id]]
  return []
}

interface TaskAssigneeAvatarsProps {
  names: string[]
  max?: number
  className?: string
}

export function TaskAssigneeAvatars({ names, max = 3, className }: TaskAssigneeAvatarsProps) {
  if (!names.length) return null
  const shown = names.slice(0, max)
  const extra = names.length - shown.length

  return (
    <div className={cn("flex items-center -space-x-1.5", className)}>
      {shown.map((name, i) => (
        <Avatar key={`${name}-${i}`} className="h-5 w-5 border-2 border-card">
          <AvatarFallback className="text-[9px] bg-accent text-white">
            {name[0]?.toUpperCase() ?? "?"}
          </AvatarFallback>
        </Avatar>
      ))}
      {extra > 0 && (
        <span className="ml-1 text-[10px] text-muted-foreground">+{extra}</span>
      )}
    </div>
  )
}
