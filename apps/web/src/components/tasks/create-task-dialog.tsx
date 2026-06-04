"use client"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { FolderOpen, Calendar, Flag } from "lucide-react"
import { MemberMultiSelect } from "@/components/tasks/member-multi-select"

// ── Types ─────────────────────────────────────────────────────

export interface TaskFormData {
  title: string
  description?: string
  priority: string
  assignee_id?: string
  assignee_ids?: string[]
  project_id?: string
  due_date?: string
  source_message_id?: string
}

interface CreateTaskDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: TaskFormData) => void
  workspaceId: string
  defaultProjectId?: string       // pre-fill when creating from a project board
  defaultStatus?: string          // pre-fill when creating from a specific column
  sourceMessageContent?: string   // pre-fill title from a message
}

// ── Priority config ────────────────────────────────────────────

const PRIORITIES = [
  { value: "low",    label: "Low",    dot: "bg-slate-400",  ring: "border-slate-300  text-slate-600 dark:text-slate-400"  },
  { value: "medium", label: "Med",    dot: "bg-amber-400",  ring: "border-amber-300  text-amber-600 dark:text-amber-400"  },
  { value: "high",   label: "High",   dot: "bg-orange-500", ring: "border-orange-300 text-orange-600 dark:text-orange-400" },
  { value: "urgent", label: "Urgent", dot: "bg-red-500",    ring: "border-red-300    text-red-600   dark:text-red-400"    },
]

// ── Component ──────────────────────────────────────────────────

export function CreateTaskDialog({
  open,
  onOpenChange,
  onSubmit,
  workspaceId,
  defaultProjectId,
  defaultStatus,
  sourceMessageContent,
}: CreateTaskDialogProps) {
  const [title,      setTitle]      = useState(sourceMessageContent ?? "")
  const [description, setDesc]      = useState("")
  const [priority,   setPriority]   = useState("medium")
  const [assigneeIds, setAssigneeIds] = useState<string[]>([])
  const [projectId,  setProjectId]  = useState(defaultProjectId ?? "")
  const [dueDate,    setDueDate]    = useState("")

  const { data: members = [] } = useQuery<Array<{ id: string; name: string }>>({
    queryKey: ["members", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/members`).then((r) => r.data),
    staleTime: 60_000,
    enabled: open,
  })

  const { data: projects = [] } = useQuery<Array<{ id: string; name: string; status: string }>>({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/projects`).then((r) => r.data),
    staleTime: 30_000,
    enabled: open,
  })

  function handleOpen(v: boolean) {
    if (v) {
      // Reset when opening fresh
      setTitle(sourceMessageContent ?? "")
      setDesc("")
      setPriority("medium")
      setAssigneeIds([])
      setProjectId(defaultProjectId ?? "")
      setDueDate("")
    }
    onOpenChange(v)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    onSubmit({
      title: title.trim(),
      description: description.trim() || undefined,
      priority,
      assignee_ids: assigneeIds.length ? assigneeIds : undefined,
      project_id: projectId || undefined,
      due_date: dueDate || undefined,
      status: defaultStatus || "todo",
    })
    onOpenChange(false)
  }

  const selectedProject = projects.find((p) => p.id === projectId)

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-base">
            New Task
            {defaultStatus && defaultStatus !== "todo" && (
              <span className="ml-2 text-xs font-normal text-muted-foreground normal-case">
                → {defaultStatus.replace("_", " ")}
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5 pt-1">
          {/* Title — always first, always focused */}
          <Input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Task title…"
            className="text-base font-medium border-0 border-b rounded-none px-0 shadow-none focus-visible:ring-0 focus-visible:border-accent/50 transition-colors placeholder:text-muted-foreground/50"
            required
          />

          {/* Description */}
          <Textarea
            value={description}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="Add a description… (optional)"
            rows={2}
            className="resize-none text-sm border-muted/50"
          />

          {/* ── Property grid ─────────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-3">

            {/* Priority */}
            <div className="flex flex-col gap-1.5">
              <Label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Flag size={11} /> Priority
              </Label>
              <div className="flex gap-1.5">
                {PRIORITIES.map((p) => (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setPriority(p.value)}
                    className={cn(
                      "flex items-center gap-1 px-2 py-1 rounded-lg border text-xs font-medium transition-all",
                      priority === p.value
                        ? cn("border-current bg-current/10", p.ring)
                        : "border-transparent text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                    )}
                  >
                    <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", p.dot)} />
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Assignees */}
            <div className="flex flex-col gap-1.5 col-span-2">
              <Label className="text-xs text-muted-foreground">Assignees</Label>
              <MemberMultiSelect
                members={members}
                value={assigneeIds}
                onChange={setAssigneeIds}
              />
            </div>

            {/* Project */}
            <div className="flex flex-col gap-1.5">
              <Label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <FolderOpen size={11} /> Project
              </Label>
              <div className="flex items-center gap-2">
                {selectedProject && (
                  <div className="h-5 w-5 rounded bg-accent/10 flex items-center justify-center shrink-0">
                    <FolderOpen size={10} className="text-accent" />
                  </div>
                )}
                <select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  className="flex-1 text-sm bg-background border border-input rounded-lg px-2.5 py-1.5 outline-none focus:ring-1 focus:ring-accent/50 text-foreground cursor-pointer"
                >
                  <option value="">No project</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Due date */}
            <div className="flex flex-col gap-1.5">
              <Label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Calendar size={11} /> Due date
              </Label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="text-sm bg-background border border-input rounded-lg px-2.5 py-1.5 outline-none focus:ring-1 focus:ring-accent/50 text-foreground cursor-pointer w-full"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-1 border-t">
            <Button type="button" variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={!title.trim()}>
              Create task
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
