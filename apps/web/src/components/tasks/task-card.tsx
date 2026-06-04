import { TaskAssigneeAvatars, assigneeNamesForTask } from "@/components/tasks/task-assignee-avatars"
import { Calendar, FolderOpen } from "lucide-react"
import { format } from "date-fns"
import { cn } from "@/lib/utils"

const priorityConfig: Record<string, { label: string; bar: string; text: string }> = {
  low:    { label: "Low",    bar: "bg-slate-400",   text: "text-slate-500 dark:text-slate-400"   },
  medium: { label: "Medium", bar: "bg-amber-400",   text: "text-amber-600 dark:text-amber-400"   },
  high:   { label: "High",   bar: "bg-orange-500",  text: "text-orange-600 dark:text-orange-400" },
  urgent: { label: "Urgent", bar: "bg-red-500",     text: "text-red-600 dark:text-red-400"       },
}

export interface Task {
  id: string
  title: string
  description?: string
  priority: string
  status: string
  due_date?: string | null
  assignee_id?: string | null
  assignee_ids?: string[]
  assignee_names?: string[]
  project_id?: string | null
  tags?: string[]
}

export function TaskCard({
  task,
  onClick,
  memberMap,
  projectName,
}: {
  task: Task
  onClick: () => void
  memberMap?: Record<string, string>
  projectName?: string
}) {
  const assigneeNames = assigneeNamesForTask(task, memberMap)
  const priority = priorityConfig[task.priority] ?? priorityConfig.medium
  const isOverdue =
    task.due_date &&
    new Date(task.due_date) < new Date() &&
    task.status !== "done"

  return (
    <div
      onClick={onClick}
      className={cn(
        "group relative bg-card border rounded-xl p-3.5 cursor-pointer",
        "hover:shadow-md hover:border-border/80 transition-all duration-150",
        "flex flex-col gap-2.5"
      )}
    >
      {/* Priority bar on the left edge */}
      <span
        className={cn(
          "absolute left-0 top-3 bottom-3 w-[3px] rounded-full",
          priority.bar
        )}
      />

      {/* Title */}
      <p className="text-sm font-medium leading-snug pr-1 pl-1">{task.title}</p>

      {/* Description */}
      {task.description && (
        <p className="text-xs text-muted-foreground line-clamp-2 pl-1">{task.description}</p>
      )}

      {/* Project badge — only in global view */}
      {projectName && (
        <div className="flex items-center gap-1 pl-1">
          <FolderOpen size={9} className="text-accent/60 shrink-0" />
          <span className="text-[10px] text-accent/70 font-medium truncate">{projectName}</span>
        </div>
      )}

      {/* Footer: priority label + due date + assignee */}
      <div className="flex items-center justify-between gap-2 pl-1">
        <span className={cn("text-xs font-medium", priority.text)}>
          {priority.label}
        </span>

        <div className="flex items-center gap-2 ml-auto">
          {task.due_date && (
            <span
              className={cn(
                "flex items-center gap-1 text-xs",
                isOverdue ? "text-red-500 dark:text-red-400" : "text-muted-foreground"
              )}
            >
              <Calendar size={10} />
              {format(new Date(task.due_date), "MMM d")}
            </span>
          )}
          <TaskAssigneeAvatars names={assigneeNames} />
        </div>
      </div>
    </div>
  )
}
