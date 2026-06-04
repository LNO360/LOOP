"use client"
import { useState } from "react"
import { Circle, Clock, CheckCircle2, XCircle, Calendar, FolderOpen, ChevronDown, ChevronRight } from "lucide-react"
import { TaskAssigneeAvatars, assigneeNamesForTask } from "@/components/tasks/task-assignee-avatars"
import { cn } from "@/lib/utils"
import { format } from "date-fns"
import type { Task } from "./kanban-board"

// ── Config ─────────────────────────────────────────────────────

const statusIcon: Record<string, React.ElementType> = {
  todo:        Circle,
  in_progress: Clock,
  done:        CheckCircle2,
  cancelled:   XCircle,
}
const statusColor: Record<string, string> = {
  todo:        "text-slate-400",
  in_progress: "text-blue-500",
  done:        "text-emerald-500",
  cancelled:   "text-rose-500",
}
const priorityDot: Record<string, string> = {
  low:    "bg-slate-400",
  medium: "bg-amber-400",
  high:   "bg-orange-500",
  urgent: "bg-red-500",
}
const CYCLE: Record<string, string> = {
  todo: "in_progress",
  in_progress: "done",
  done: "cancelled",
  cancelled: "todo",
}

// ── Single task row ────────────────────────────────────────────

function TaskRow({
  task,
  memberMap,
  projectMap,
  showProject,
  onTaskClick,
  onStatusChange,
}: {
  task: Task
  memberMap: Record<string, string>
  projectMap?: Record<string, string>
  showProject?: boolean
  onTaskClick: (task: Task) => void
  onStatusChange: (taskId: string, status: string) => void
}) {
  const StatusIconRow = statusIcon[task.status] ?? Circle
  const isOverdue =
    task.due_date &&
    new Date(task.due_date) < new Date() &&
    task.status !== "done"
  const projectName = task.project_id && projectMap ? projectMap[task.project_id] : null

  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 bg-card hover:bg-muted/30 transition-colors group/row cursor-pointer"
      onClick={() => onTaskClick(task)}
    >
      {/* Status toggle */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onStatusChange(task.id, CYCLE[task.status] ?? "todo")
        }}
        className="shrink-0 p-0.5 rounded hover:bg-muted transition-colors"
        title={`Move to ${CYCLE[task.status]}`}
      >
        <StatusIconRow size={16} className={cn(statusColor[task.status], "transition-colors")} />
      </button>

      {/* Title */}
      <span
        className={cn(
          "flex-1 text-sm font-medium min-w-0 truncate",
          task.status === "done" && "line-through text-muted-foreground",
          task.status === "cancelled" && "text-muted-foreground"
        )}
      >
        {task.title}
      </span>

      {/* Project badge (only in non-grouped views) */}
      {showProject && projectName && (
        <div className="hidden sm:flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-accent/8 border border-accent/15 shrink-0">
          <FolderOpen size={9} className="text-accent/60" />
          <span className="text-[10px] text-accent/70 font-medium max-w-[100px] truncate">{projectName}</span>
        </div>
      )}

      {/* Tags */}
      {task.tags && task.tags.length > 0 && (
        <div className="hidden sm:flex items-center gap-1">
          {task.tags.slice(0, 2).map((tag) => (
            <span key={tag} className="text-xs bg-muted text-muted-foreground px-1.5 py-0.5 rounded-full font-medium">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Priority dot */}
      <div className="hidden sm:flex items-center gap-1.5 w-20 shrink-0">
        <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", priorityDot[task.priority])} />
        <span className="text-xs text-muted-foreground capitalize">{task.priority}</span>
      </div>

      {/* Due date */}
      <div className="hidden md:flex items-center gap-1 w-24 shrink-0">
        {task.due_date ? (
          <>
            <Calendar size={11} className={isOverdue ? "text-red-500" : "text-muted-foreground"} />
            <span className={cn("text-xs", isOverdue ? "text-red-500 font-medium" : "text-muted-foreground")}>
              {format(new Date(task.due_date), "MMM d")}
            </span>
          </>
        ) : (
          <span className="text-xs text-muted-foreground/30">No date</span>
        )}
      </div>

      {/* Assignees */}
      <div className="w-16 shrink-0 flex justify-end">
        {(() => {
          const names = assigneeNamesForTask(task, memberMap)
          return names.length ? (
            <TaskAssigneeAvatars names={names} />
          ) : (
            <div className="h-6 w-6 rounded-full border-2 border-dashed border-muted-foreground/20" />
          )
        })()}
      </div>
    </div>
  )
}

// ── Collapsible group ──────────────────────────────────────────

function TaskGroup({
  label,
  icon,
  tasks,
  memberMap,
  projectMap,
  showProject,
  onTaskClick,
  onStatusChange,
  defaultOpen = true,
}: {
  label: string
  icon?: React.ReactNode
  tasks: Task[]
  memberMap: Record<string, string>
  projectMap?: Record<string, string>
  showProject?: boolean
  onTaskClick: (task: Task) => void
  onStatusChange: (taskId: string, status: string) => void
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 mb-2 px-1 w-full text-left group/hdr"
      >
        {open
          ? <ChevronDown size={13} className="text-muted-foreground/60 shrink-0" />
          : <ChevronRight size={13} className="text-muted-foreground/60 shrink-0" />
        }
        {icon}
        <span className="text-sm font-semibold">{label}</span>
        <span className="text-xs text-muted-foreground bg-muted rounded-full px-2 py-0.5 font-medium">
          {tasks.length}
        </span>
      </button>

      {open && (
        <div className="border rounded-xl overflow-hidden divide-y mb-2">
          {tasks.length === 0 ? (
            <div className="px-4 py-3 text-sm text-muted-foreground/50 italic">No tasks</div>
          ) : (
            tasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                memberMap={memberMap}
                projectMap={projectMap}
                showProject={showProject}
                onTaskClick={onTaskClick}
                onStatusChange={onStatusChange}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── Props ──────────────────────────────────────────────────────

interface TaskListViewProps {
  tasks: Task[]
  memberMap: Record<string, string>
  projectMap?: Record<string, string>   // project_id → project name
  groupByProject?: boolean              // show project-grouped view
  onTaskClick: (task: Task) => void
  onStatusChange: (taskId: string, status: string) => void
}

// ── Main component ─────────────────────────────────────────────

export function TaskListView({
  tasks,
  memberMap,
  projectMap,
  groupByProject,
  onTaskClick,
  onStatusChange,
}: TaskListViewProps) {
  // ── Group by project mode ──────────────────────────────────
  if (groupByProject && projectMap) {
    const projectIds = Object.keys(projectMap)
    const grouped: Record<string, Task[]> = {}
    const noProject: Task[] = []

    for (const task of tasks) {
      if (task.project_id && projectMap[task.project_id]) {
        ;(grouped[task.project_id] ??= []).push(task)
      } else {
        noProject.push(task)
      }
    }

    return (
      <div className="space-y-4">
        {projectIds
          .filter((pid) => grouped[pid]?.length)
          .map((pid) => (
            <TaskGroup
              key={pid}
              label={projectMap[pid]}
              icon={<FolderOpen size={13} className="text-accent/70 shrink-0" />}
              tasks={grouped[pid]}
              memberMap={memberMap}
              onTaskClick={onTaskClick}
              onStatusChange={onStatusChange}
            />
          ))}

        {noProject.length > 0 && (
          <TaskGroup
            label="No Project"
            icon={<FolderOpen size={13} className="text-muted-foreground/40 shrink-0" />}
            tasks={noProject}
            memberMap={memberMap}
            onTaskClick={onTaskClick}
            onStatusChange={onStatusChange}
            defaultOpen={projectIds.length === 0}
          />
        )}

        {tasks.length === 0 && (
          <p className="text-sm text-muted-foreground/60 italic px-1">No tasks found.</p>
        )}
      </div>
    )
  }

  // ── Default: group by status ───────────────────────────────
  const STATUS_GROUPS = [
    { id: "todo",        label: "To Do"       },
    { id: "in_progress", label: "In Progress" },
    { id: "done",        label: "Done"        },
    { id: "cancelled",   label: "Cancelled"   },
  ]

  return (
    <div className="space-y-6">
      {STATUS_GROUPS.map((grp) => {
        const grpTasks = tasks.filter((t) => t.status === grp.id)
        if (!grpTasks.length && grp.id === "cancelled") return null
        const StatusIcon = statusIcon[grp.id]
        return (
          <TaskGroup
            key={grp.id}
            label={grp.label}
            icon={<StatusIcon size={14} className={cn(statusColor[grp.id], "shrink-0")} />}
            tasks={grpTasks}
            memberMap={memberMap}
            projectMap={projectMap}
            showProject={true}
            onTaskClick={onTaskClick}
            onStatusChange={onStatusChange}
          />
        )
      })}
    </div>
  )
}
