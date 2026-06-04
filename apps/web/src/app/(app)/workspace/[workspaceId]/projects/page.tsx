"use client"
import { use, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import {
  FolderOpen,
  Plus,
  ChevronRight,
  Brain,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Circle,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useRunProjectManager } from "@/hooks/use-agents"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"

// ── Types ─────────────────────────────────────────────────────

interface Project {
  id: string
  name: string
  description?: string
  status: string
}

interface Task {
  id: string
  status: string
}

interface ProjectManagerResult {
  health: "on_track" | "at_risk" | "blocked"
  summary: string
  blockers: string[]
  suggestions: string[]
}

// ── Config maps ───────────────────────────────────────────────

const statusConfig: Record<string, { label: string; bg: string; text: string }> = {
  active:    { label: "Active",    bg: "bg-emerald-500/10", text: "text-emerald-600 dark:text-emerald-400" },
  on_hold:   { label: "On Hold",   bg: "bg-amber-500/10",   text: "text-amber-600 dark:text-amber-400"   },
  completed: { label: "Completed", bg: "bg-blue-500/10",    text: "text-blue-500"                        },
  cancelled: { label: "Cancelled", bg: "bg-slate-500/10",   text: "text-slate-500"                       },
  planned:   { label: "Planned",   bg: "bg-purple-500/10",  text: "text-purple-500"                      },
}

const healthConfig = {
  on_track: { icon: CheckCircle2, color: "text-emerald-500", label: "On Track", bg: "bg-emerald-500/10" },
  at_risk:  { icon: AlertTriangle, color: "text-amber-500",  label: "At Risk",  bg: "bg-amber-500/10"  },
  blocked:  { icon: XCircle,       color: "text-red-500",    label: "Blocked",   bg: "bg-red-500/10"   },
}

// ── useCreateProject hook ─────────────────────────────────────

function useCreateProject(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string; status?: string }) =>
      api.post(`/workspaces/${workspaceId}/projects`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects", workspaceId] }),
  })
}

// ── Task stats per project ────────────────────────────────────

function useProjectTasks(workspaceId: string, projectId: string) {
  return useQuery<Task[]>({
    queryKey: ["tasks", workspaceId, { project_id: projectId }],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/tasks`, { params: { project_id: projectId } })
        .then((r) => r.data),
    staleTime: 30_000,
  })
}

// ── Status Chip ───────────────────────────────────────────────

function StatusChip({ status }: { status: string }) {
  const cfg = statusConfig[status] ?? { label: status, bg: "bg-muted", text: "text-muted-foreground" }
  return (
    <span className={cn("text-xs px-2 py-0.5 rounded-full capitalize font-medium", cfg.bg, cfg.text)}>
      {cfg.label}
    </span>
  )
}

// ── Health Badge ──────────────────────────────────────────────

function HealthBadge({ health }: { health: string | null }) {
  if (!health) {
    return (
      <div className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg w-fit font-medium bg-muted text-muted-foreground">
        <Circle size={11} /> Not analyzed
      </div>
    )
  }
  const cfg = healthConfig[health as keyof typeof healthConfig]
  if (!cfg) return null
  const Icon = cfg.icon
  return (
    <div className={cn("flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg w-fit font-medium", cfg.bg, cfg.color)}>
      <Icon size={11} /> {cfg.label}
    </div>
  )
}

// ── Progress Bar ──────────────────────────────────────────────

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
      <div
        className="h-full rounded-full bg-accent transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ── Project Card ──────────────────────────────────────────────

function ProjectCard({
  workspaceId,
  project,
}: {
  workspaceId: string
  project: Project
}) {
  const router = useRouter()
  const { mutateAsync: analyze, isPending } = useRunProjectManager(workspaceId)
  const [pmData, setPmData] = useState<ProjectManagerResult | null>(null)
  const [expanded, setExpanded] = useState(false)

  const { data: tasks = [] } = useProjectTasks(workspaceId, project.id)
  const doneCount = tasks.filter((t) => t.status === "done").length
  const total = tasks.length
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0

  async function handleAnalyze(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    try {
      const result = await analyze({ project_id: project.id, project_name: project.name })
      setPmData(result)
      setExpanded(true)
    } catch {
      /* silently fail */
    }
  }

  return (
    <div
      className="rounded-xl border bg-card p-5 flex flex-col gap-4 hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => router.push(`/workspace/${workspaceId}/projects/${project.id}`)}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="h-9 w-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
          <FolderOpen size={16} className="text-accent" />
        </div>
        <StatusChip status={project.status} />
      </div>

      {/* Name + description */}
      <div className="flex flex-col gap-1">
        <p className="font-semibold text-sm leading-snug">{project.name}</p>
        {project.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
            {project.description}
          </p>
        )}
      </div>

      {/* Task stats */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {doneCount}/{total} task{total !== 1 ? "s" : ""} done
          </span>
          <span className="font-medium text-foreground">{pct}%</span>
        </div>
        <ProgressBar pct={pct} />
      </div>

      {/* Health badge (shown after analysis) */}
      <HealthBadge health={pmData ? pmData.health : null} />

      {/* Analyze button */}
      {!pmData ? (
        <button
          onClick={handleAnalyze}
          disabled={isPending}
          className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border hover:bg-muted/50 transition-colors disabled:opacity-50 text-muted-foreground hover:text-foreground justify-center"
        >
          {isPending ? <Loader2 size={11} className="animate-spin" /> : <Brain size={11} />}
          {isPending ? "Analyzing…" : "PM Analysis"}
        </button>
      ) : (
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v) }}
          className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground justify-between"
        >
          <span className="flex items-center gap-1.5">
            <Brain size={11} /> PM Analysis
          </span>
          {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
        </button>
      )}

      {/* Expanded PM panel */}
      {pmData && expanded && (
        <div className="pt-3 border-t space-y-2">
          <p className="text-xs text-muted-foreground leading-relaxed">{pmData.summary}</p>
          {pmData.blockers.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                Blockers
              </p>
              <ul className="space-y-0.5">
                {pmData.blockers.map((b, i) => (
                  <li key={i} className="text-xs text-red-500">
                    ⚠ {b}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {pmData.suggestions.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                Suggestions
              </p>
              <ul className="space-y-0.5">
                {pmData.suggestions.map((s, i) => (
                  <li key={i} className="text-xs text-muted-foreground">
                    → {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <button
            onClick={() => {
              setPmData(null)
              setExpanded(false)
            }}
            className="text-[10px] text-muted-foreground hover:text-foreground"
          >
            Clear
          </button>
        </div>
      )}

      {/* Footer: open project detail */}
      <div
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mt-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <Link
          href={`/workspace/${workspaceId}/projects/${project.id}`}
          className="flex items-center gap-1 hover:text-accent"
        >
          Open project <ChevronRight size={11} />
        </Link>
      </div>
    </div>
  )
}

// ── Create Project Modal ──────────────────────────────────────

const STATUS_OPTIONS = [
  { value: "active",  label: "Active"   },
  { value: "planned", label: "Planned"  },
  { value: "on_hold", label: "On Hold"  },
]

function CreateProjectModal({
  workspaceId,
  open,
  onClose,
}: {
  workspaceId: string
  open: boolean
  onClose: () => void
}) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [status, setStatus] = useState("active")
  const { mutate: create, isPending } = useCreateProject(workspaceId)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    create(
      { name: name.trim(), description: description.trim() || undefined, status },
      {
        onSuccess: () => {
          setName("")
          setDescription("")
          setStatus("active")
          onClose()
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Project</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 pt-1">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="proj-name">Name *</Label>
            <Input
              id="proj-name"
              autoFocus
              placeholder="e.g. OLT Monitoring Dashboard"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="proj-desc">Description</Label>
            <Textarea
              id="proj-desc"
              placeholder="What is this project about?"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Status</Label>
            <div className="flex gap-2">
              {STATUS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setStatus(opt.value)}
                  className={cn(
                    "flex-1 text-xs py-1.5 rounded-lg border transition-colors",
                    status === opt.value
                      ? "border-accent bg-accent/10 text-accent font-medium"
                      : "text-muted-foreground hover:bg-muted/50"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={isPending || !name.trim()}>
              {isPending ? <Loader2 size={13} className="animate-spin mr-1.5" /> : null}
              Create Project
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── Filter Pills ──────────────────────────────────────────────

const FILTER_OPTIONS = [
  { value: "all",       label: "All"       },
  { value: "active",    label: "Active"    },
  { value: "on_hold",   label: "On Hold"   },
  { value: "completed", label: "Completed" },
]

// ── Main Page ─────────────────────────────────────────────────

export default function ProjectsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = use(params)
  const [modalOpen, setModalOpen] = useState(false)
  const [filter, setFilter] = useState("all")

  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/projects`).then((r) => r.data),
  })

  const filtered =
    filter === "all" ? projects : projects.filter((p) => p.status === filter)

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-3.5 border-b shrink-0">
        <h1 className="text-lg font-semibold mr-2">Projects</h1>
        <span className="text-xs text-muted-foreground">
          {projects.length} project{projects.length !== 1 ? "s" : ""}
        </span>
        <div className="ml-auto">
          <Button onClick={() => setModalOpen(true)} size="sm" className="gap-1.5 h-8">
            <Plus size={14} /> New Project
          </Button>
        </div>
      </div>

      {/* Filter pills */}
      {projects.length > 0 && (
        <div className="flex gap-1.5 px-6 py-3 border-b shrink-0">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFilter(opt.value)}
              className={cn(
                "text-xs px-3 py-1 rounded-full transition-colors",
                filter === opt.value
                  ? "bg-accent text-white font-medium"
                  : "text-muted-foreground hover:bg-muted"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 size={14} className="animate-spin" /> Loading projects…
          </div>
        ) : projects.length === 0 ? (
          // Empty state
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <div className="h-12 w-12 rounded-xl bg-muted flex items-center justify-center mb-4">
              <FolderOpen size={20} className="text-muted-foreground" />
            </div>
            <p className="text-sm font-medium mb-1">No projects yet</p>
            <p className="text-xs text-muted-foreground mb-4">
              Projects help you group related tasks together
            </p>
            <Button
              onClick={() => setModalOpen(true)}
              size="sm"
              variant="outline"
              className="gap-1.5"
            >
              <Plus size={13} /> Create your first project
            </Button>
          </div>
        ) : filtered.length === 0 ? (
          // Filter empty state
          <div className="flex flex-col items-center justify-center h-40 text-center">
            <p className="text-sm text-muted-foreground">No projects match this filter.</p>
            <button
              onClick={() => setFilter("all")}
              className="text-xs text-accent hover:underline mt-2"
            >
              Show all
            </button>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((p) => (
              <ProjectCard key={p.id} workspaceId={workspaceId} project={p} />
            ))}
          </div>
        )}
      </div>

      {/* Create modal */}
      <CreateProjectModal
        workspaceId={workspaceId}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  )
}
