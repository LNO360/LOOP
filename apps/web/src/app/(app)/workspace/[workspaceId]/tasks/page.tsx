"use client"
import { use, useState } from "react"
import { useTasks, useCreateTask, useUpdateTask } from "@/hooks/use-tasks"
import { KanbanBoard, type Task } from "@/components/tasks/kanban-board"
import { TaskListView } from "@/components/tasks/task-list-view"
import { CreateTaskDialog } from "@/components/tasks/create-task-dialog"
import { TaskDetailPanel } from "@/components/tasks/task-detail-panel"
import { Button } from "@/components/ui/button"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { cn } from "@/lib/utils"
import {
  Plus, LayoutGrid, List, Filter, ChevronDown, X,
  Users, FolderOpen, Layers,
} from "lucide-react"

// ── Types ─────────────────────────────────────────────────────

type View  = "board" | "list"
type Scope = "all" | "mine" | "no_project"

const PRIORITY_OPTS = ["low", "medium", "high", "urgent"] as const
const STATUS_OPTS   = ["todo", "in_progress", "done", "cancelled"] as const

// ── Scope tabs config ─────────────────────────────────────────

const SCOPE_TABS: { id: Scope; label: string; icon: React.ElementType }[] = [
  { id: "all",        label: "All Tasks",   icon: Layers     },
  { id: "mine",       label: "My Tasks",    icon: Users      },
  { id: "no_project", label: "No Project",  icon: FolderOpen },
]

// ── Page ──────────────────────────────────────────────────────

export default function TasksPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = use(params)
  const currentUser = useAuthStore((s) => s.user)
  const currentUserId = currentUser?.id ?? ""

  const [view,         setView]         = useState<View>("list")
  const [scope,        setScope]        = useState<Scope>("all")
  const [createOpen,   setCreateOpen]   = useState(false)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)

  // Filters (only visible when showFilters is open)
  const [filterPriority, setFilterPriority] = useState("")
  const [filterStatus,   setFilterStatus]   = useState("")
  const [filterAssignee, setFilterAssignee] = useState("")
  const [filterProject,  setFilterProject]  = useState("")
  const [showFilters,    setShowFilters]    = useState(false)

  // Data
  const { data: rawTasks = [], isLoading } = useTasks(workspaceId)
  const { mutate: createTask }  = useCreateTask(workspaceId)
  const { mutate: updateTask }  = useUpdateTask(workspaceId)

  const { data: rawMembers = [] } = useQuery<Array<{ id: string; name: string }>>({
    queryKey: ["members", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/members`).then((r) => r.data),
    staleTime: 60_000,
  })
  const { data: rawProjects = [] } = useQuery<Array<{ id: string; name: string; status: string }>>({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/projects`).then((r) => r.data),
    staleTime: 30_000,
  })

  const members    = rawMembers
  const projects   = rawProjects
  const memberMap  = Object.fromEntries(members.map((m) => [m.id, m.name]))
  const projectMap = Object.fromEntries(projects.map((p) => [p.id, p.name]))

  // ── Scope filter ─────────────────────────────────────────────
  function taskHasAssignee(t: Task, userId: string) {
    if (t.assignee_ids?.includes(userId)) return true
    return t.assignee_id === userId
  }

  const scopedTasks = (rawTasks as Task[]).filter((t) => {
    if (scope === "mine" && currentUserId) return taskHasAssignee(t, currentUserId)
    if (scope === "no_project") return !t.project_id
    return true
  })

  // ── Attribute filters ─────────────────────────────────────────
  const tasks = scopedTasks.filter((t) => {
    if (filterPriority && t.priority !== filterPriority) return false
    if (filterStatus   && t.status   !== filterStatus)   return false
    if (filterAssignee && !taskHasAssignee(t, filterAssignee)) return false
    if (filterProject  && t.project_id  !== filterProject)  return false
    return true
  })

  const activeFilters = [filterPriority, filterStatus, filterAssignee, filterProject].filter(Boolean).length

  function handleStatusChange(taskId: string, status: string) {
    updateTask({ taskId, data: { status } })
    if (selectedTask?.id === taskId) setSelectedTask((t) => t ? { ...t, status } : null)
  }

  function handleTaskUpdate(taskId: string, data: Record<string, unknown>) {
    updateTask({ taskId, data })
    setSelectedTask((t) => {
      if (!t) return null
      const next = { ...t, ...data } as Task
      if (Array.isArray(data.assignee_ids)) {
        const ids = data.assignee_ids as string[]
        next.assignee_ids = ids
        next.assignee_names = ids.map((id) => memberMap[id]).filter(Boolean)
        next.assignee_id = ids[0] ?? null
      }
      return next
    })
  }

  // In "All" list view: group by project for clarity
  const useProjectGrouping = scope === "all" && view === "list"

  return (
    <div className="flex flex-col h-full bg-background">
      {/* ── Header ────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-6 py-3.5 border-b shrink-0 flex-wrap gap-y-2">
        <h1 className="text-lg font-semibold mr-1">Tasks</h1>

        {/* Scope tabs */}
        <div className="flex items-center bg-muted/60 rounded-lg p-0.5 gap-0.5">
          {SCOPE_TABS.map((tab) => {
            const Icon = tab.icon
            const count = (rawTasks as Task[]).filter((t) => {
              if (tab.id === "mine" && currentUserId) return taskHasAssignee(t, currentUserId)
              if (tab.id === "no_project") return !t.project_id
              return true
            }).length
            return (
              <button
                key={tab.id}
                onClick={() => setScope(tab.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  scope === tab.id
                    ? "bg-background shadow-sm text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon size={12} />
                {tab.label}
                <span className={cn(
                  "tabular-nums text-[10px] rounded-full px-1.5 py-0.5 font-semibold",
                  scope === tab.id ? "bg-accent/15 text-accent" : "text-muted-foreground"
                )}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>

        {/* View toggle */}
        <div className="flex items-center bg-muted/60 rounded-lg p-0.5 gap-0.5">
          <button
            onClick={() => setView("list")}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors",
              view === "list"
                ? "bg-background shadow-sm text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <List size={12} /> List
          </button>
          <button
            onClick={() => setView("board")}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors",
              view === "board"
                ? "bg-background shadow-sm text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <LayoutGrid size={12} /> Board
          </button>
        </div>

        {/* Filter toggle */}
        <button
          onClick={() => setShowFilters((v) => !v)}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors",
            showFilters || activeFilters > 0
              ? "bg-accent/10 text-accent border-accent/30"
              : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted"
          )}
        >
          <Filter size={12} />
          Filter
          {activeFilters > 0 && (
            <span className="bg-accent text-white rounded-full text-[10px] w-4 h-4 flex items-center justify-center font-bold">
              {activeFilters}
            </span>
          )}
        </button>

        {/* Task count */}
        <span className="text-xs text-muted-foreground hidden sm:block">
          {tasks.length} task{tasks.length !== 1 ? "s" : ""}
          {activeFilters > 0 && ` (filtered from ${scopedTasks.length})`}
        </span>

        <div className="ml-auto">
          <Button onClick={() => setCreateOpen(true)} size="sm" className="gap-1.5 h-8">
            <Plus size={14} /> New task
          </Button>
        </div>
      </div>

      {/* ── Filter bar ────────────────────────────────────────── */}
      {showFilters && (
        <div className="flex items-center gap-3 px-6 py-2.5 border-b bg-muted/20 shrink-0 flex-wrap gap-y-2">
          {/* Priority */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Priority:</span>
            <div className="flex gap-1">
              {PRIORITY_OPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => setFilterPriority(filterPriority === p ? "" : p)}
                  className={cn(
                    "text-xs px-2 py-0.5 rounded-full font-medium capitalize border transition-colors",
                    filterPriority === p
                      ? "bg-accent/15 text-accent border-accent/40"
                      : "border-transparent text-muted-foreground hover:bg-muted"
                  )}
                >{p}</button>
              ))}
            </div>
          </div>

          <div className="w-px h-4 bg-border" />

          {/* Status */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Status:</span>
            <div className="flex gap-1">
              {STATUS_OPTS.map((s) => (
                <button
                  key={s}
                  onClick={() => setFilterStatus(filterStatus === s ? "" : s)}
                  className={cn(
                    "text-xs px-2 py-0.5 rounded-full font-medium capitalize border transition-colors",
                    filterStatus === s
                      ? "bg-accent/15 text-accent border-accent/40"
                      : "border-transparent text-muted-foreground hover:bg-muted"
                  )}
                >{s.replace("_", " ")}</button>
              ))}
            </div>
          </div>

          <div className="w-px h-4 bg-border" />

          {/* Project filter */}
          {projects.length > 0 && (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Project:</span>
                <select
                  value={filterProject}
                  onChange={(e) => setFilterProject(e.target.value)}
                  className="text-xs bg-transparent border border-border rounded-md px-2 py-0.5 outline-none text-foreground cursor-pointer"
                >
                  <option value="">Any project</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div className="w-px h-4 bg-border" />
            </>
          )}

          {/* Assignee filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Assignee:</span>
            <select
              value={filterAssignee}
              onChange={(e) => setFilterAssignee(e.target.value)}
              className="text-xs bg-transparent border border-border rounded-md px-2 py-0.5 outline-none text-foreground cursor-pointer"
            >
              <option value="">Anyone</option>
              {members.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </div>

          {activeFilters > 0 && (
            <button
              onClick={() => { setFilterPriority(""); setFilterStatus(""); setFilterAssignee(""); setFilterProject("") }}
              className="ml-auto flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <X size={12} /> Clear all
            </button>
          )}
        </div>
      )}

      {/* ── Grouping hint (list + all scope) ───────────────────── */}
      {useProjectGrouping && projects.length > 0 && !showFilters && (
        <div className="px-6 py-2 border-b bg-muted/10 shrink-0 flex items-center gap-2">
          <FolderOpen size={11} className="text-accent/60" />
          <span className="text-xs text-muted-foreground">Grouped by project</span>
        </div>
      )}

      {/* ── Main content ──────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
            Loading tasks…
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="h-12 w-12 rounded-xl bg-muted flex items-center justify-center">
              <Layers size={20} className="text-muted-foreground" />
            </div>
            <p className="text-sm font-medium">
              {scope === "mine" ? "No tasks assigned to you" :
               scope === "no_project" ? "All tasks are in projects" :
               "No tasks yet"}
            </p>
            <p className="text-xs text-muted-foreground">
              {scope === "all" && "Create your first task to get started"}
              {scope === "mine" && "Tasks assigned to you will appear here"}
              {scope === "no_project" && "Tasks without a project will appear here"}
            </p>
            {scope === "all" && (
              <Button size="sm" variant="outline" className="gap-1.5 mt-1" onClick={() => setCreateOpen(true)}>
                <Plus size={13} /> Create task
              </Button>
            )}
          </div>
        ) : view === "board" ? (
          <div className="h-full overflow-hidden p-6">
            <KanbanBoard
              tasks={tasks}
              memberMap={memberMap}
              projectMap={projectMap}
              onTaskClick={setSelectedTask}
              onStatusChange={handleStatusChange}
            />
          </div>
        ) : (
          <div className="h-full overflow-y-auto p-6">
            <TaskListView
              tasks={tasks}
              memberMap={memberMap}
              projectMap={projectMap}
              groupByProject={useProjectGrouping}
              onTaskClick={setSelectedTask}
              onStatusChange={handleStatusChange}
            />
          </div>
        )}
      </div>

      {/* Create dialog — now with priority, assignee, project */}
      <CreateTaskDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        workspaceId={workspaceId}
        onSubmit={(data) => createTask(data as unknown as Record<string, unknown>)}
      />

      {/* Detail panel — now with project property */}
      <TaskDetailPanel
        task={selectedTask}
        workspaceId={workspaceId}
        memberMap={memberMap}
        members={members}
        projects={projects}
        onClose={() => setSelectedTask(null)}
        onUpdate={handleTaskUpdate}
        onDeleted={() => setSelectedTask(null)}
      />
    </div>
  )
}
