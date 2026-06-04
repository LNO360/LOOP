"use client"
import { use, useState, useRef, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useProjectTasks, useUpdateTask } from "@/hooks/use-tasks"
import { useRunProjectManager } from "@/hooks/use-agents"
import { CreateTaskDialog } from "@/components/tasks/create-task-dialog"
import { TaskCard, type Task } from "@/components/tasks/task-card"
import { TaskDetailPanel } from "@/components/tasks/task-detail-panel"
import {
  ArrowLeft, Plus, Brain, Loader2, CheckCircle2, AlertTriangle,
  XCircle, FolderOpen, Pencil, Check, X, Trash2,
} from "lucide-react"
import { DeleteProjectDialog } from "@/components/projects/delete-project-dialog"
import { cn } from "@/lib/utils"
import Link from "next/link"

// ── Types ─────────────────────────────────────────────────────

interface Project {
  id: string
  name: string
  description?: string
  status: string
}

interface Member {
  id: string
  name: string
}

interface PMResult {
  health: "on_track" | "at_risk" | "blocked"
  summary: string
  blockers: string[]
  suggestions: string[]
}

// ── Column config ──────────────────────────────────────────────

const COLUMNS = [
  { id: "todo",        label: "To Do",       color: "text-slate-500",   dot: "bg-slate-400",   border: "" },
  { id: "in_progress", label: "In Progress", color: "text-blue-600",    dot: "bg-blue-400",    border: "border-blue-200/50 dark:border-blue-800/40" },
  { id: "done",        label: "Done",        color: "text-emerald-600", dot: "bg-emerald-400", border: "border-emerald-200/50 dark:border-emerald-800/40" },
]

const healthConfig = {
  on_track: { icon: CheckCircle2,  color: "text-emerald-600", label: "On Track", bg: "bg-emerald-500/10" },
  at_risk:  { icon: AlertTriangle, color: "text-amber-600",   label: "At Risk",  bg: "bg-amber-500/10"  },
  blocked:  { icon: XCircle,       color: "text-red-600",     label: "Blocked",  bg: "bg-red-500/10"    },
}

const statusColors: Record<string, string> = {
  active:    "text-emerald-600 bg-emerald-500/10",
  planned:   "text-purple-600 bg-purple-500/10",
  on_hold:   "text-amber-600 bg-amber-500/10",
  completed: "text-blue-600 bg-blue-500/10",
  cancelled: "text-slate-500 bg-slate-500/10",
}

// ── Hooks ─────────────────────────────────────────────────────

function useProject(workspaceId: string, projectId: string) {
  return useQuery<Project>({
    queryKey: ["project", projectId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/projects/${projectId}`).then((r) => r.data),
  })
}

function useCreateProjectTask(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.post(`/workspaces/${workspaceId}/tasks`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks", workspaceId] }),
  })
}

function useUpdateProject(workspaceId: string, projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name?: string; description?: string; status?: string }) =>
      api.patch(`/workspaces/${workspaceId}/projects/${projectId}`, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project", projectId] })
      qc.invalidateQueries({ queryKey: ["projects", workspaceId] })
    },
  })
}

// ── Status selector ────────────────────────────────────────────

function StatusSelector({ workspaceId, project }: { workspaceId: string; project: Project }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const { mutate: update } = useUpdateProject(workspaceId, project.id)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const options = ["active", "planned", "on_hold", "completed", "cancelled"]

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn("text-xs px-2.5 py-1.5 rounded-lg capitalize font-medium transition-colors", statusColors[project.status] ?? "text-muted-foreground bg-muted")}
      >
        {project.status.replace("_", " ")}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-30 bg-popover border rounded-xl shadow-lg py-1 min-w-[130px]">
          {options.map((s) => (
            <button
              key={s}
              onClick={() => { update({ status: s }); setOpen(false) }}
              className={cn("flex items-center w-full px-3 py-1.5 text-xs transition-colors hover:bg-muted capitalize", project.status === s ? "font-semibold text-accent" : "")}
            >
              {s.replace("_", " ")}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Kanban Column ──────────────────────────────────────────────

function KanbanColumn({
  col,
  tasks,
  workspaceId,
  memberMap,
  members,
  projects,
  onTaskClick,
  onStatusChange,
  onAddTask,
}: {
  col: typeof COLUMNS[0]
  tasks: Task[]
  workspaceId: string
  memberMap: Record<string, string>
  members: Member[]
  projects: Project[]
  onTaskClick: (task: Task) => void
  onStatusChange: (taskId: string, status: string) => void
  onAddTask: (status: string) => void
}) {
  return (
    <div className={cn("flex flex-col rounded-xl border bg-muted/20 overflow-hidden", col.border)}>
      {/* Column header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b bg-muted/10">
        <span className={cn("h-2 w-2 rounded-full shrink-0", col.dot)} />
        <span className={cn("text-xs font-semibold flex-1", col.color)}>{col.label}</span>
        <span className="text-[10px] font-semibold tabular-nums text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
          {tasks.length}
        </span>
        {/* The ONE creation entry point per column */}
        <button
          onClick={() => onAddTask(col.id)}
          title={`New task in ${col.label}`}
          className="p-0.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
        >
          <Plus size={13} />
        </button>
      </div>

      {/* Task cards — same component as Tasks page */}
      <div className="flex flex-col gap-2 p-3 flex-1 overflow-y-auto">
        {tasks.length === 0 ? (
          <button
            onClick={() => onAddTask(col.id)}
            className="flex items-center justify-center gap-2 py-6 text-xs text-muted-foreground/50 border-2 border-dashed border-muted-foreground/15 rounded-lg hover:border-accent/30 hover:text-accent/60 transition-colors"
          >
            <Plus size={12} /> Add first task
          </button>
        ) : (
          tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onClick={() => onTaskClick(task)}
              memberMap={memberMap}
            />
          ))
        )}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ workspaceId: string; projectId: string }>
}) {
  const { workspaceId, projectId } = use(params)

  // Data
  const { data: project, isLoading: projectLoading } = useProject(workspaceId, projectId)
  const { data: tasks = [], isLoading: tasksLoading } = useProjectTasks(workspaceId, projectId)
  const { mutate: updateTask } = useUpdateTask(workspaceId)
  const { mutate: createTask } = useCreateProjectTask(workspaceId)
  const { mutateAsync: analyze, isPending: analyzing } = useRunProjectManager(workspaceId)

  const { data: members = [] } = useQuery<Member[]>({
    queryKey: ["members", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/members`).then((r) => r.data),
    staleTime: 60_000,
  })
  const memberMap = Object.fromEntries(members.map((m) => [m.id, m.name]))

  // Projects list (for task detail panel project switcher)
  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/projects`).then((r) => r.data),
    staleTime: 30_000,
  })

  // UI state
  const [selectedTask,   setSelectedTask]   = useState<Task | null>(null)
  const [createStatus,   setCreateStatus]   = useState<string | null>(null) // which column triggered create
  const [pmData,         setPmData]         = useState<PMResult | null>(null)
  const [editingName,    setEditingName]    = useState(false)
  const [nameVal,        setNameVal]        = useState("")
  const [deleteOpen,     setDeleteOpen]     = useState(false)
  const nameRef = useRef<HTMLInputElement>(null)
  const { mutate: updateProject } = useUpdateProject(workspaceId, projectId)

  useEffect(() => {
    if (editingName) nameRef.current?.focus()
  }, [editingName])

  useEffect(() => {
    if (project) setNameVal(project.name)
  }, [project?.name])

  function saveName() {
    const t = nameVal.trim()
    if (t && t !== project?.name) updateProject({ name: t })
    setEditingName(false)
  }

  function handleStatusChange(taskId: string, status: string) {
    updateTask({ taskId, data: { status } })
    if (selectedTask?.id === taskId) setSelectedTask((t) => t ? { ...t, status } : null)
  }

  function handleTaskUpdate(taskId: string, data: Record<string, unknown>) {
    updateTask({ taskId, data })
    setSelectedTask((t) => t ? { ...t, ...data } as Task : null)
  }

  async function handleAnalyze() {
    if (!project) return
    try {
      const result = await analyze({ project_id: project.id, project_name: project.name })
      setPmData(result)
    } catch { /* silent */ }
  }

  // Loading
  if (projectLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={20} className="animate-spin text-muted-foreground" />
      </div>
    )
  }
  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <FolderOpen size={32} className="text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Project not found</p>
        <Link href={`/workspace/${workspaceId}/projects`} className="text-xs text-accent hover:underline">
          ← Back to projects
        </Link>
      </div>
    )
  }

  const tasksByStatus = {
    todo:        tasks.filter((t) => t.status === "todo"),
    in_progress: tasks.filter((t) => t.status === "in_progress"),
    done:        tasks.filter((t) => t.status === "done"),
  }
  const doneCount = tasksByStatus.done.length
  const total = tasks.length
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      {/* ── Header ────────────────────────────────────────────── */}
      <div className="border-b px-6 py-4 shrink-0">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-3 text-xs text-muted-foreground">
          <Link href={`/workspace/${workspaceId}/tasks`} className="hover:text-foreground transition-colors">
            Tasks
          </Link>
          <span className="text-muted-foreground/40">/</span>
          <Link href={`/workspace/${workspaceId}/projects`} className="hover:text-foreground transition-colors">
            Projects
          </Link>
          <span className="text-muted-foreground/40">/</span>
          <span className="text-foreground font-medium">{project.name}</span>
        </div>

        <div className="flex items-start gap-4 justify-between">
          {/* Left: icon + name + description + stats */}
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div className="h-10 w-10 rounded-xl bg-accent/10 flex items-center justify-center shrink-0">
              <FolderOpen size={18} className="text-accent" />
            </div>
            <div className="flex-1 min-w-0">
              {/* Editable name */}
              {editingName ? (
                <div className="flex items-center gap-2 mb-1">
                  <input
                    ref={nameRef}
                    value={nameVal}
                    onChange={(e) => setNameVal(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveName()
                      if (e.key === "Escape") { setEditingName(false); setNameVal(project.name) }
                    }}
                    className="text-xl font-bold bg-transparent border-b-2 border-accent outline-none flex-1"
                  />
                  <button onClick={saveName} className="text-accent"><Check size={14} /></button>
                  <button onClick={() => { setEditingName(false); setNameVal(project.name) }} className="text-muted-foreground"><X size={14} /></button>
                </div>
              ) : (
                <button
                  onClick={() => setEditingName(true)}
                  className="group flex items-center gap-2 text-xl font-bold hover:text-muted-foreground transition-colors mb-0.5 text-left"
                >
                  {project.name}
                  <Pencil size={12} className="opacity-0 group-hover:opacity-40 transition-opacity" />
                </button>
              )}

              {project.description && (
                <p className="text-sm text-muted-foreground mb-2">{project.description}</p>
              )}

              {/* Progress stats */}
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span><b className="text-slate-500 font-semibold">{tasksByStatus.todo.length}</b> to do</span>
                  <span><b className="text-blue-500 font-semibold">{tasksByStatus.in_progress.length}</b> in progress</span>
                  <span><b className="text-emerald-500 font-semibold">{doneCount}</b> done</span>
                </div>
                {total > 0 && (
                  <div className="flex items-center gap-2 max-w-32">
                    <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-[10px] text-muted-foreground tabular-nums">{pct}%</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right: PM analysis + status + new task */}
          <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
            {pmData ? (
              (() => {
                const cfg = healthConfig[pmData.health]
                const Icon = cfg.icon
                return (
                  <button
                    onClick={() => setPmData(null)}
                    className={cn("flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg font-medium", cfg.bg, cfg.color)}
                    title="Click to dismiss"
                  >
                    <Icon size={12} /> {cfg.label}
                  </button>
                )
              })()
            ) : (
              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border hover:bg-muted/50 transition-colors disabled:opacity-50 text-muted-foreground hover:text-foreground"
              >
                {analyzing ? <Loader2 size={12} className="animate-spin" /> : <Brain size={12} />}
                {analyzing ? "Analyzing…" : "PM Analysis"}
              </button>
            )}

            <StatusSelector workspaceId={workspaceId} project={project} />

            {/* Global "+ New Task" for this project */}
            <button
              onClick={() => setCreateStatus("todo")}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors font-medium"
            >
              <Plus size={13} /> New task
            </button>
          </div>
        </div>

        {/* PM analysis panel — inline below header */}
        {pmData && (
          <div className="mt-4 pt-4 border-t grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <p className="text-muted-foreground font-medium mb-1">Summary</p>
              <p className="text-foreground/80 leading-relaxed">{pmData.summary}</p>
            </div>
            {pmData.blockers.length > 0 && (
              <div>
                <p className="text-red-500 font-medium mb-1">Blockers</p>
                <ul className="space-y-0.5">{pmData.blockers.map((b, i) => <li key={i} className="text-red-500/80">⚠ {b}</li>)}</ul>
              </div>
            )}
            {pmData.suggestions.length > 0 && (
              <div>
                <p className="text-muted-foreground font-medium mb-1">Suggestions</p>
                <ul className="space-y-0.5">{pmData.suggestions.map((s, i) => <li key={i} className="text-muted-foreground">→ {s}</li>)}</ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Kanban board ──────────────────────────────────────── */}
      {tasksLoading ? (
        <div className="flex items-center justify-center flex-1">
          <Loader2 size={16} className="animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="flex-1 overflow-x-auto flex flex-col min-h-0">
          <div className="grid grid-cols-3 gap-4 p-6 flex-1 min-w-[640px]">
            {COLUMNS.map((col) => (
              <KanbanColumn
                key={col.id}
                col={col}
                tasks={tasksByStatus[col.id as keyof typeof tasksByStatus]}
                workspaceId={workspaceId}
                memberMap={memberMap}
                members={members}
                projects={projects}
                onTaskClick={setSelectedTask}
                onStatusChange={handleStatusChange}
                onAddTask={(status) => setCreateStatus(status)}
              />
            ))}
          </div>

          {/* Danger zone — deliberate, not one-click */}
          <div className="border-t px-6 py-5 shrink-0 bg-muted/20">
            <p className="text-xs font-medium text-muted-foreground mb-1">Danger zone</p>
            <p className="text-[11px] text-muted-foreground/80 mb-3 max-w-lg">
              Deleting a project is permanent. Tasks stay in your workspace but are unlinked from
              this project.
            </p>
            <button
              type="button"
              onClick={() => setDeleteOpen(true)}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-destructive/30 text-destructive hover:bg-destructive/10 transition-colors"
            >
              <Trash2 size={13} />
              Delete project…
            </button>
          </div>
        </div>
      )}

      <DeleteProjectDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        workspaceId={workspaceId}
        project={{ id: project.id, name: project.name }}
        taskCount={total}
      />

      {/* ── Create task dialog (same component as Tasks page) ─── */}
      <CreateTaskDialog
        open={createStatus !== null}
        onOpenChange={(v) => { if (!v) setCreateStatus(null) }}
        workspaceId={workspaceId}
        defaultProjectId={projectId}
        defaultStatus={createStatus ?? undefined}
        onSubmit={(data) => {
          createTask(data as unknown as Record<string, unknown>)
          setCreateStatus(null)
        }}
      />

      {/* ── Task detail panel (same component as Tasks page) ──── */}
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
