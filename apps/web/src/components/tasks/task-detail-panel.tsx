"use client"
import { useEffect, useRef, useState } from "react"
import {
  X, Calendar, User, Tag, MessageSquare,
  Send, Trash2, ChevronDown, Circle, CheckCircle2,
  Clock, AlertCircle, XCircle, FolderOpen,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import { formatDistanceToNow, format } from "date-fns"
import { useTaskComments, useAddComment, useDeleteComment } from "@/hooks/use-task-comments"
import { useAuthStore } from "@/store/auth"
import { DocEditor } from "@/components/docs/doc-editor"
import { useDebouncedCallback } from "use-debounce"
import { useSubtasks, useCreateSubtask, useUpdateSubtask } from "@/hooks/use-subtasks"
import { useDeleteTask } from "@/hooks/use-tasks"
import { MemberMultiSelect } from "@/components/tasks/member-multi-select"

/* ─── types ──────────────────────────────────────────────────────────── */
export interface TaskDetail {
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

interface SubtaskItem {
  id: string
  title: string
  status: string
  priority: string
}

/* ─── config ─────────────────────────────────────────────────────────── */
const STATUS_OPTIONS = [
  { value: "todo",        label: "To Do",        Icon: Circle,        color: "text-slate-400" },
  { value: "in_progress", label: "In Progress",   Icon: Clock,         color: "text-blue-500"  },
  { value: "done",        label: "Done",          Icon: CheckCircle2,  color: "text-emerald-500" },
  { value: "cancelled",   label: "Cancelled",     Icon: XCircle,       color: "text-rose-500"  },
]
const PRIORITY_OPTIONS = [
  { value: "low",    label: "Low",    dot: "bg-slate-400",  text: "text-slate-500 dark:text-slate-400" },
  { value: "medium", label: "Medium", dot: "bg-amber-400",  text: "text-amber-600 dark:text-amber-400" },
  { value: "high",   label: "High",   dot: "bg-orange-500", text: "text-orange-600 dark:text-orange-400" },
  { value: "urgent", label: "Urgent", dot: "bg-red-500",    text: "text-red-600 dark:text-red-400" },
]

/* ─── prop-row helper ────────────────────────────────────────────────── */
function PropRow({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ElementType
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-start min-h-[34px] gap-3 group/row">
      <div className="flex items-center gap-2 w-36 shrink-0 pt-0.5">
        <Icon size={14} className="text-muted-foreground/60 shrink-0" />
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="flex-1 flex items-center flex-wrap gap-1.5 min-w-0 pt-0.5">
        {children}
      </div>
    </div>
  )
}

/* ─── comment ────────────────────────────────────────────────────────── */
function CommentItem({
  comment,
  currentUserId,
  onDelete,
}: {
  comment: { id: string; author_name: string; content: string; created_at: string; author_id: string }
  currentUserId?: string
  onDelete: () => void
}) {
  return (
    <div className="flex gap-3 group/comment">
      <Avatar className="h-7 w-7 shrink-0 mt-0.5">
        <AvatarFallback className="text-[11px] bg-accent text-white">
          {comment.author_name[0].toUpperCase()}
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 mb-0.5">
          <span className="text-sm font-medium">{comment.author_name}</span>
          <span className="text-xs text-muted-foreground">
            {formatDistanceToNow(new Date(comment.created_at), { addSuffix: true })}
          </span>
        </div>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{comment.content}</p>
      </div>
      {comment.author_id === currentUserId && (
        <button
          onClick={onDelete}
          className="opacity-0 group-hover/comment:opacity-100 transition-opacity p-1 text-muted-foreground hover:text-destructive rounded"
        >
          <Trash2 size={13} />
        </button>
      )}
    </div>
  )
}

/* ─── main component ─────────────────────────────────────────────────── */
interface TaskDetailPanelProps {
  task: TaskDetail | null
  workspaceId: string
  memberMap: Record<string, string>
  members: Array<{ id: string; name: string }>
  projects?: Array<{ id: string; name: string }>
  onClose: () => void
  onUpdate: (taskId: string, data: Record<string, unknown>) => void
  onDeleted?: (taskId: string) => void
}

export function TaskDetailPanel({
  task,
  workspaceId,
  memberMap,
  members,
  projects = [],
  onClose,
  onUpdate,
  onDeleted,
}: TaskDetailPanelProps) {
  const [visible, setVisible] = useState(false)
  const [title, setTitle] = useState("")
  const [status, setStatus] = useState("todo")
  const [priority, setPriority] = useState("medium")
  const [dueDate, setDueDate] = useState("")
  const [assigneeIds, setAssigneeIds] = useState<string[]>([])
  const [projectId, setProjectId] = useState("")
  const [tagInput, setTagInput] = useState("")
  const [tags, setTags] = useState<string[]>([])
  const [commentText, setCommentText] = useState("")
  const [addingSubtask, setAddingSubtask] = useState(false)
  const [subtaskTitle, setSubtaskTitle] = useState("")
  const commentRef = useRef<HTMLTextAreaElement>(null)

  const currentUser = useAuthStore((s) => s.user)
  const { data: comments = [] } = useTaskComments(workspaceId, task?.id ?? null)
  const { mutate: addComment } = useAddComment(workspaceId, task?.id ?? "")
  const { mutate: deleteComment } = useDeleteComment(workspaceId, task?.id ?? "")
  const { data: subtasks = [] } = useSubtasks(workspaceId, task?.id ?? null)
  const { mutate: createSubtask } = useCreateSubtask(workspaceId)
  const { mutate: updateSubtask } = useUpdateSubtask(workspaceId, task?.id ?? "")
  const { mutate: deleteTask, isPending: deleting } = useDeleteTask(workspaceId)

  // Debounced description save
  const saveDescription = useDebouncedCallback((json: unknown) => {
    if (!task) return
    onUpdate(task.id, { description: JSON.stringify(json) })
  }, 1200)

  useEffect(() => {
    if (task) {
      setTitle(task.title)
      setStatus(task.status)
      setPriority(task.priority)
      setDueDate(task.due_date ?? "")
      setAssigneeIds(
        task.assignee_ids?.length
          ? task.assignee_ids
          : task.assignee_id
            ? [task.assignee_id]
            : []
      )
      setProjectId(task.project_id ?? "")
      setTags(task.tags ?? [])
      requestAnimationFrame(() => setVisible(true))
    } else {
      setVisible(false)
    }
  }, [task?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  function save(patch: Record<string, unknown>) {
    if (!task) return
    onUpdate(task.id, patch)
  }

  function handleClose() {
    setVisible(false)
    setTimeout(onClose, 220)
  }

  function handleDelete() {
    if (!task || deleting) return
    const subtaskNote =
      subtasks.length > 0
        ? ` This will also delete ${subtasks.length} subtask${subtasks.length === 1 ? "" : "s"}.`
        : ""
    if (!confirm(`Delete "${task.title}"? This cannot be undone.${subtaskNote}`)) return
    deleteTask(task.id, {
      onSuccess: () => {
        setVisible(false)
        onDeleted?.(task.id)
        onClose()
      },
    })
  }

  function handleAddTag(e: React.KeyboardEvent) {
    if ((e.key === "Enter" || e.key === ",") && tagInput.trim()) {
      e.preventDefault()
      const newTag = tagInput.trim().toLowerCase().replace(/,/g, "")
      if (!tags.includes(newTag)) {
        const next = [...tags, newTag]
        setTags(next)
        save({ tags: next })
      }
      setTagInput("")
    }
  }

  function removeTag(tag: string) {
    const next = tags.filter((t) => t !== tag)
    setTags(next)
    save({ tags: next })
  }

  function submitComment() {
    if (!commentText.trim()) return
    addComment(commentText.trim())
    setCommentText("")
  }

  if (!task) return null

  const statusCfg = STATUS_OPTIONS.find((s) => s.value === status) ?? STATUS_OPTIONS[0]
  const priorityCfg = PRIORITY_OPTIONS.find((p) => p.value === priority) ?? PRIORITY_OPTIONS[1]

  let descContent: unknown = task.description
  try {
    if (task.description) descContent = JSON.parse(task.description)
  } catch { /* plain text */ }

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 bg-black/50 z-40 backdrop-blur-[3px] transition-opacity duration-200",
          visible ? "opacity-100" : "opacity-0"
        )}
        onClick={handleClose}
      />

      {/* Modal — centred, Notion-style */}
      <div
        className={cn(
          "fixed inset-x-0 mx-auto z-50 flex flex-col",
          "top-[5vh] bottom-[5vh] w-full max-w-3xl",
          "bg-background rounded-2xl border shadow-2xl overflow-hidden",
          "transition-all duration-220 ease-out",
          visible ? "opacity-100 scale-100 translate-y-0" : "opacity-0 scale-[0.97] translate-y-4"
        )}
      >
        {/* ── toolbar ──────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-6 py-3.5 border-b shrink-0">
          <div className="flex items-center gap-2">
            <statusCfg.Icon size={15} className={statusCfg.color} />
            <span className="text-sm text-muted-foreground font-medium">
              {statusCfg.label}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
              onClick={handleDelete}
              disabled={deleting}
              title="Delete task"
            >
              <Trash2 size={15} />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleClose}>
              <X size={15} />
            </Button>
          </div>
        </div>

        {/* ── scrollable body ───────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto">
          {/* Title */}
          <div className="px-8 pt-7 pb-2">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={() => title !== task.title && save({ title })}
              className="text-2xl font-bold border-none shadow-none px-0 h-auto focus-visible:ring-0 bg-transparent tracking-tight"
              placeholder="Task title"
            />
          </div>

          {/* ── Properties ───────────────────────────────────────── */}
          <div className="px-8 py-4 space-y-1 border-b">

            {/* Status */}
            <PropRow icon={statusCfg.Icon} label="Status">
              <div className="relative">
                <select
                  value={status}
                  onChange={(e) => { setStatus(e.target.value); save({ status: e.target.value }) }}
                  className={cn(
                    "text-sm font-medium bg-transparent border-0 outline-none cursor-pointer appearance-none pr-4",
                    statusCfg.color
                  )}
                >
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <ChevronDown size={12} className="absolute right-0 top-1.5 text-muted-foreground pointer-events-none" />
              </div>
            </PropRow>

            {/* Priority */}
            <PropRow icon={AlertCircle} label="Priority">
              <div className="relative flex items-center gap-1.5">
                <span className={cn("h-2 w-2 rounded-full shrink-0", priorityCfg.dot)} />
                <select
                  value={priority}
                  onChange={(e) => { setPriority(e.target.value); save({ priority: e.target.value }) }}
                  className={cn(
                    "text-sm font-medium bg-transparent border-0 outline-none cursor-pointer appearance-none pr-4",
                    priorityCfg.text
                  )}
                >
                  {PRIORITY_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <ChevronDown size={12} className="text-muted-foreground pointer-events-none" />
              </div>
            </PropRow>

            {/* Assignees */}
            <PropRow icon={User} label="Assignees">
              <div className="min-w-[200px] flex-1">
                <MemberMultiSelect
                  members={members}
                  value={assigneeIds}
                  onChange={(ids) => {
                    setAssigneeIds(ids)
                    save({ assignee_ids: ids })
                  }}
                  placeholder="Add assignees…"
                />
              </div>
            </PropRow>

            {/* Project */}
            {projects.length > 0 && (
              <PropRow icon={FolderOpen} label="Project">
                <div className="relative flex items-center gap-2">
                  {projectId && projects.find((p) => p.id === projectId) && (
                    <div className="h-4 w-4 rounded bg-accent/10 flex items-center justify-center shrink-0">
                      <FolderOpen size={9} className="text-accent" />
                    </div>
                  )}
                  <select
                    value={projectId}
                    onChange={(e) => {
                      setProjectId(e.target.value)
                      save({ project_id: e.target.value || undefined })
                    }}
                    className="text-sm bg-transparent border-0 outline-none cursor-pointer appearance-none pr-4 text-foreground"
                  >
                    <option value="">No project</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                  <ChevronDown size={12} className="text-muted-foreground pointer-events-none" />
                </div>
              </PropRow>
            )}

            {/* Due date */}
            <PropRow icon={Calendar} label="Due date">
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={dueDate}
                  onChange={(e) => { setDueDate(e.target.value); save({ due_date: e.target.value }) }}
                  className="text-sm bg-transparent border-0 outline-none cursor-pointer text-foreground"
                />
                {dueDate && (
                  <span className="text-xs text-muted-foreground">
                    ({format(new Date(dueDate), "MMM d, yyyy")})
                  </span>
                )}
              </div>
            </PropRow>

            {/* Tags */}
            <PropRow icon={Tag} label="Tags">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 text-xs bg-muted px-2 py-0.5 rounded-full font-medium text-muted-foreground hover:bg-muted/80"
                >
                  {tag}
                  <button onClick={() => removeTag(tag)} className="hover:text-foreground ml-0.5">
                    <X size={10} />
                  </button>
                </span>
              ))}
              <input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleAddTag}
                placeholder="Add tag…"
                className="text-xs bg-transparent outline-none border-0 text-muted-foreground placeholder:text-muted-foreground/40 w-20"
              />
            </PropRow>
          </div>

          {/* ── Description ──────────────────────────────────────── */}
          <div className="px-8 py-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Description
            </p>
            <div className="prose dark:prose-invert max-w-none min-h-[120px]">
              <DocEditor
                content={descContent}
                onChange={saveDescription}
                className="text-sm"
              />
            </div>
          </div>

          {/* ── Subtasks ─────────────────────────────────────────── */}
          <div className="px-8 pb-5">
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Subtasks
                </span>
                {subtasks.length > 0 && (
                  <span className="text-xs text-muted-foreground">
                    {subtasks.filter((s: SubtaskItem) => s.status === "done").length}/{subtasks.length}
                  </span>
                )}
              </div>

              <div className="space-y-1">
                {subtasks.map((sub: SubtaskItem) => (
                  <div key={sub.id} className="flex items-center gap-2 group/sub py-0.5">
                    <button
                      onClick={() => updateSubtask({ taskId: sub.id, data: { status: sub.status === "done" ? "todo" : "done" } })}
                      className={cn(
                        "h-4 w-4 rounded border-2 shrink-0 flex items-center justify-center transition-colors",
                        sub.status === "done"
                          ? "bg-emerald-500 border-emerald-500 text-white"
                          : "border-muted-foreground/30 hover:border-accent"
                      )}
                    >
                      {sub.status === "done" && <span className="text-[10px]">✓</span>}
                    </button>
                    <span className={cn(
                      "text-sm flex-1",
                      sub.status === "done" && "line-through text-muted-foreground"
                    )}>
                      {sub.title}
                    </span>
                  </div>
                ))}
              </div>

              {/* Add subtask input */}
              {addingSubtask ? (
                <div className="flex items-center gap-2 mt-2">
                  <div className="h-4 w-4 rounded border-2 border-muted-foreground/20 shrink-0" />
                  <input
                    autoFocus
                    value={subtaskTitle}
                    onChange={(e) => setSubtaskTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && subtaskTitle.trim()) {
                        createSubtask({ title: subtaskTitle.trim(), parent_task_id: task.id, priority: "medium" })
                        setSubtaskTitle("")
                        setAddingSubtask(false)
                      }
                      if (e.key === "Escape") { setSubtaskTitle(""); setAddingSubtask(false) }
                    }}
                    onBlur={() => { setSubtaskTitle(""); setAddingSubtask(false) }}
                    placeholder="Subtask title…"
                    className="flex-1 text-sm bg-transparent outline-none border-b border-accent/40 pb-0.5"
                  />
                </div>
              ) : (
                <button
                  onClick={() => setAddingSubtask(true)}
                  className="flex items-center gap-2 mt-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <span className="text-base leading-none">+</span> Add subtask
                </button>
              )}
            </div>
          </div>

          {/* ── Comments ─────────────────────────────────────────── */}
          <div className="px-8 pb-8">
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare size={14} className="text-muted-foreground" />
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Comments
              </p>
              {comments.length > 0 && (
                <span className="text-xs bg-muted text-muted-foreground px-1.5 rounded-full font-medium">
                  {comments.length}
                </span>
              )}
            </div>

            <div className="space-y-4 mb-5">
              {comments.length === 0 ? (
                <p className="text-sm text-muted-foreground/60 italic">
                  No comments yet. Be the first!
                </p>
              ) : (
                comments.map((c) => (
                  <CommentItem
                    key={c.id}
                    comment={c}
                    currentUserId={currentUser?.id}
                    onDelete={() => deleteComment(c.id)}
                  />
                ))
              )}
            </div>

            {/* Comment input */}
            <div className="flex gap-3 items-start">
              <Avatar className="h-7 w-7 shrink-0 mt-0.5">
                <AvatarFallback className="text-[11px] bg-accent text-white">
                  {currentUser?.name?.[0]?.toUpperCase() ?? "U"}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 border rounded-xl bg-muted/20 focus-within:bg-background focus-within:ring-1 focus-within:ring-accent/50 transition-all">
                <Textarea
                  ref={commentRef}
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      submitComment()
                    }
                  }}
                  placeholder="Add a comment… (Enter to send, Shift+Enter for newline)"
                  rows={2}
                  className="border-0 bg-transparent resize-none text-sm focus-visible:ring-0 shadow-none"
                />
                <div className="flex justify-end px-3 pb-2">
                  <Button
                    size="sm"
                    className="h-7 text-xs gap-1.5"
                    disabled={!commentText.trim()}
                    onClick={submitComment}
                  >
                    <Send size={12} /> Send
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
