"use client"
import { use, useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useTasks } from "@/hooks/use-tasks"
import { useNotifications, useMarkRead, useMarkAllRead } from "@/hooks/use-notifications"
import { useIntegrations } from "@/hooks/use-integrations"
import { useAuthStore } from "@/store/auth"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import {
  format,
  startOfWeek,
  endOfWeek,
  isToday,
  isTomorrow,
  differenceInDays,
  formatDistanceToNow,
} from "date-fns"
import { cn } from "@/lib/utils"
import {
  CheckSquare,
  AlertTriangle,
  Calendar,
  TrendingUp,
  Bell,
  ArrowRight,
  Hash,
  FileText,
  Sparkles,
  Plus,
  AtSign,
  ListChecks,
  CalendarDays,
  CheckCheck,
  BellOff,
  CheckCircle2,
  X,
  Plug,
} from "lucide-react"
import Link from "next/link"

// ── Types ──────────────────────────────────────────────────────────────────
interface Task {
  id: string
  title: string
  description?: string
  priority: "urgent" | "high" | "medium" | "low" | string
  status: string
  due_date?: string
  assignee_id?: string
}

interface Notification {
  id: string
  type?: "mention" | "task" | "digest" | string
  message: string
  read: boolean
  created_at: string
}

interface NotifData {
  notifications: Notification[]
  unread_count: number
}

// ── Constants ──────────────────────────────────────────────────────────────
const PRIORITY_ORDER: Record<string, number> = { urgent: 0, high: 1, medium: 2, low: 3 }

const PRIORITY_DOT: Record<string, string> = {
  urgent: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-amber-400",
  low: "bg-slate-400",
}

const PRIORITY_LABEL: Record<string, string> = {
  urgent: "Urgent",
  high: "High",
  medium: "Medium",
  low: "Low",
}

// ── Helpers ────────────────────────────────────────────────────────────────
function dueDateLabel(dateStr: string, today: string): { label: string; urgent: boolean } {
  const d = new Date(dateStr + "T00:00:00")
  if (dateStr < today) return { label: "Overdue", urgent: true }
  if (isToday(d)) return { label: "Today", urgent: true }
  if (isTomorrow(d)) return { label: "Tomorrow", urgent: false }
  const days = differenceInDays(d, new Date())
  return { label: `${days}d`, urgent: false }
}

function notifIcon(type?: string) {
  if (type === "mention") return <AtSign size={14} className="text-blue-400 shrink-0 mt-0.5" />
  if (type === "task") return <ListChecks size={14} className="text-amber-400 shrink-0 mt-0.5" />
  return <CalendarDays size={14} className="text-violet-400 shrink-0 mt-0.5" />
}

// ── SetupChecklist ─────────────────────────────────────────────────────────
function SetupChecklist({ workspaceId }: { workspaceId: string }) {
  const storageKey = `lno_setup_dismissed_${workspaceId}`
  const [dismissed, setDismissed] = useState(false)
  const router = useRouter()

  useEffect(() => {
    setDismissed(localStorage.getItem(storageKey) === "1")
  }, [storageKey])

  const { data: ws } = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}`).then((r) => r.data),
    staleTime: 60_000,
  })
  const { data: members = [] } = useQuery({
    queryKey: ["members", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/members`).then((r) => r.data),
    staleTime: 60_000,
  })
  const { data: integrations } = useIntegrations(workspaceId)

  const googleConnected = integrations?.integrations?.find((i: { provider: string; connected: boolean }) => i.provider === "google")?.connected ?? false
  const githubConnected = integrations?.github_app?.installed ?? false
  const teamInvited = Array.isArray(members) && members.length > 1

  const items = [
    { done: true,            label: "Create workspace",          action: null },
    { done: teamInvited,     label: "Invite a teammate",         action: () => router.push(`/workspace/${workspaceId}/settings`) },
    { done: googleConnected, label: "Connect Google Workspace",  action: () => router.push(`/workspace/${workspaceId}/agents?tab=settings`) },
    { done: githubConnected, label: "Install GitHub App",        action: () => router.push(`/workspace/${workspaceId}/agents?tab=settings`) },
    { done: false,           label: "Chat with Hermes",          action: () => router.push(`/workspace/${workspaceId}/agents?tab=chat`) },
  ]

  const doneCount = items.filter((i) => i.done).length
  const allDone = doneCount === items.length

  if (dismissed || allDone) return null

  return (
    <div className="rounded-xl border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-accent" />
          <span className="text-sm font-semibold">Get started with {ws?.emoji ?? "🚀"} {ws?.name ?? "your workspace"}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">{doneCount} / {items.length}</span>
          <button
            onClick={() => { localStorage.setItem(storageKey, "1"); setDismissed(true) }}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Progress */}
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all duration-500"
          style={{ width: `${(doneCount / items.length) * 100}%` }}
        />
      </div>

      <div className="grid sm:grid-cols-2 gap-2">
        {items.map(({ done, label, action }) => (
          <button
            key={label}
            onClick={action ?? undefined}
            disabled={done || !action}
            className={cn(
              "flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-left transition-colors",
              done
                ? "opacity-60 cursor-default"
                : action
                ? "hover:bg-muted/60 cursor-pointer"
                : "cursor-default"
            )}
          >
            <CheckCircle2
              size={15}
              className={done ? "text-emerald-500 shrink-0" : "text-muted-foreground/30 shrink-0"}
            />
            <span className={done ? "line-through text-muted-foreground" : ""}>{label}</span>
            {!done && action && <ArrowRight size={11} className="ml-auto text-muted-foreground" />}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Component ──────────────────────────────────────────────────────────────
export default function DashboardPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = use(params)
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const today = format(new Date(), "yyyy-MM-dd")

  // Data fetching
  const { data: allTasks = [] } = useTasks(workspaceId)
  const { data: notifRaw } = useNotifications()
  const markRead = useMarkRead()
  const markAllRead = useMarkAllRead()

  const { data: channels = [] } = useQuery({
    queryKey: ["channels", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/channels`).then((r) => r.data),
  })

  // ── Compute stats ────────────────────────────────────────────────────────
  const tasks = allTasks as Task[]
  const activeTasks = tasks.filter((t) => t.status !== "done" && t.status !== "cancelled")
  const myTasks = tasks.filter((t) => {
    if (!user?.id) return false
    if (t.assignee_ids?.includes(user.id)) return true
    return t.assignee_id === user.id
  })
  const myActive = myTasks.filter((t) => t.status !== "done" && t.status !== "cancelled")

  const overdue = activeTasks.filter((t) => t.due_date && t.due_date < today)
  const dueToday = activeTasks.filter((t) => t.due_date === today)

  const weekStart = format(startOfWeek(new Date()), "yyyy-MM-dd")
  const weekEnd = format(endOfWeek(new Date()), "yyyy-MM-dd")
  const doneThisWeek = tasks.filter(
    (t) =>
      t.status === "done" &&
      t.due_date &&
      t.due_date >= weekStart &&
      t.due_date <= weekEnd
  )

  // My tasks sorted by priority then due date
  const sortedMyTasks = [...myActive]
    .sort((a, b) => {
      const pDiff = (PRIORITY_ORDER[a.priority] ?? 3) - (PRIORITY_ORDER[b.priority] ?? 3)
      if (pDiff !== 0) return pDiff
      if (!a.due_date) return 1
      if (!b.due_date) return -1
      return a.due_date.localeCompare(b.due_date)
    })
    .slice(0, 8)

  // Notifications
  const notifData = notifRaw as NotifData | undefined
  const allNotifs = (notifData?.notifications ?? []) as Notification[]
  const unreadNotifs = allNotifs.filter((n) => !n.read)
  const recentNotifs = allNotifs.slice(0, 5)
  const hasUnread = unreadNotifs.length > 0

  // Greeting
  const hour = new Date().getHours()
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
  const firstName = user?.name?.split(" ")[0] ?? ""

  // Quick actions
  const quickActions = [
    {
      icon: Plus,
      label: "New Task",
      onClick: () => router.push(`/workspace/${workspaceId}/tasks`),
      accent: false,
    },
    {
      icon: Hash,
      label: "Channels",
      onClick: () => router.push(`/workspace/${workspaceId}/channels`),
      accent: false,
    },
    {
      icon: FileText,
      label: "New Doc",
      onClick: () => router.push(`/workspace/${workspaceId}/docs`),
      accent: false,
    },
    {
      icon: Sparkles,
      label: "Ask AI",
      onClick: () => router.push(`/workspace/${workspaceId}/agents?tab=chat`),
      accent: true,
    },
  ]

  // ── Stat cards config ────────────────────────────────────────────────────
  const stats = [
    {
      icon: CheckSquare,
      label: "Active Tasks",
      value: activeTasks.length,
      color: "text-blue-500",
      bg: "bg-blue-500/10",
      ring: "ring-blue-500/20",
    },
    {
      icon: Calendar,
      label: "Due Today",
      value: dueToday.length,
      color: "text-amber-500",
      bg: "bg-amber-500/10",
      ring: "ring-amber-500/20",
    },
    {
      icon: AlertTriangle,
      label: "Overdue",
      value: overdue.length,
      color: overdue.length > 0 ? "text-red-500" : "text-muted-foreground",
      bg: overdue.length > 0 ? "bg-red-500/10" : "bg-muted/40",
      ring: overdue.length > 0 ? "ring-red-500/20" : "ring-transparent",
    },
    {
      icon: TrendingUp,
      label: "Done This Week",
      value: doneThisWeek.length,
      color: "text-emerald-500",
      bg: "bg-emerald-500/10",
      ring: "ring-emerald-500/20",
    },
  ]

  return (
    <div className="p-6 max-w-6xl space-y-8">
      <SetupChecklist workspaceId={workspaceId} />
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {greeting}{firstName ? `, ${firstName}` : ""} 👋
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            {new Date().toLocaleDateString("en-US", {
              weekday: "long",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>
        {hasUnread && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-500/10 text-red-500 text-xs font-medium">
            <Bell size={11} />
            {unreadNotifs.length} unread
          </div>
        )}
      </div>

      {/* ── Stat cards ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(({ icon: Icon, label, value, color, bg, ring }) => (
          <div
            key={label}
            className={cn(
              "rounded-xl border bg-card p-4 ring-1 transition-shadow hover:shadow-sm",
              ring
            )}
          >
            <div className={cn("h-9 w-9 rounded-lg flex items-center justify-center mb-3", bg)}>
              <Icon size={17} className={color} />
            </div>
            <p className="text-3xl font-bold tabular-nums">{value}</p>
            <p className="text-xs text-muted-foreground mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* ── Quick actions ───────────────────────────────────────────────────── */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
          Quick Actions
        </h2>
        <div className="flex flex-wrap gap-2">
          {quickActions.map(({ icon: Icon, label, onClick, accent }) => (
            <button
              key={label}
              onClick={onClick}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-all",
                accent
                  ? "border-violet-500/40 bg-violet-500/10 text-violet-400 hover:bg-violet-500/20"
                  : "border bg-card hover:bg-muted/50 text-foreground"
              )}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
          {/* Channel shortcuts */}
          {(channels as Array<{ id: string; name: string }>).slice(0, 3).map((ch) => (
            <Link
              key={ch.id}
              href={`/workspace/${workspaceId}/channel/${ch.id}`}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border bg-card hover:bg-muted/50 transition-colors text-sm"
            >
              <Hash size={13} className="text-muted-foreground" />
              {ch.name}
            </Link>
          ))}
        </div>
      </div>

      {/* ── Main content grid ─────────────────────────────────────────────── */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* My Tasks */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold flex items-center gap-1.5">
              <CheckSquare size={14} className="text-muted-foreground" />
              My Tasks
              {myActive.length > 0 && (
                <span className="ml-1 text-xs font-normal text-muted-foreground">
                  ({myActive.length})
                </span>
              )}
            </h2>
            <Link
              href={`/workspace/${workspaceId}/tasks`}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
            >
              View all <ArrowRight size={11} />
            </Link>
          </div>

          {sortedMyTasks.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center flex flex-col items-center gap-2">
              <CheckCheck size={22} className="text-emerald-500/60" />
              <p className="text-sm font-medium text-muted-foreground">All caught up!</p>
              <p className="text-xs text-muted-foreground/60">No pending tasks assigned to you.</p>
              <button
                onClick={() => router.push(`/workspace/${workspaceId}/tasks`)}
                className="mt-2 text-xs px-3 py-1.5 rounded-lg border hover:bg-muted/50 transition-colors"
              >
                Browse tasks
              </button>
            </div>
          ) : (
            <div className="rounded-xl border overflow-hidden divide-y bg-card">
              {sortedMyTasks.map((t) => {
                const { label, urgent } = t.due_date
                  ? dueDateLabel(t.due_date, today)
                  : { label: "", urgent: false }
                return (
                  <Link
                    key={t.id}
                    href={`/workspace/${workspaceId}/tasks`}
                    className="flex items-center gap-3 px-3.5 py-2.5 hover:bg-muted/30 transition-colors group"
                  >
                    {/* Priority dot */}
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full shrink-0",
                        PRIORITY_DOT[t.priority] ?? "bg-slate-400"
                      )}
                      title={PRIORITY_LABEL[t.priority]}
                    />
                    {/* Title */}
                    <span className="flex-1 text-sm truncate group-hover:text-foreground text-foreground/90">
                      {t.title}
                    </span>
                    {/* Due label */}
                    {label && (
                      <span
                        className={cn(
                          "text-xs shrink-0 px-1.5 py-0.5 rounded font-medium",
                          urgent
                            ? "bg-red-500/10 text-red-500"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {label}
                      </span>
                    )}
                  </Link>
                )
              })}
              {myActive.length > 8 && (
                <Link
                  href={`/workspace/${workspaceId}/tasks`}
                  className="flex items-center justify-center gap-1 py-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-colors"
                >
                  +{myActive.length - 8} more tasks <ArrowRight size={11} />
                </Link>
              )}
            </div>
          )}
        </div>

        {/* Notifications */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold flex items-center gap-1.5">
              <Bell size={14} className="text-muted-foreground" />
              Notifications
              {unreadNotifs.length > 0 && (
                <span className="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-medium text-white">
                  {unreadNotifs.length}
                </span>
              )}
            </h2>
            {hasUnread && (
              <button
                onClick={() => markAllRead.mutate()}
                disabled={markAllRead.isPending}
                className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors disabled:opacity-50"
              >
                <CheckCheck size={11} />
                Mark all read
              </button>
            )}
          </div>

          {recentNotifs.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center flex flex-col items-center gap-2">
              <BellOff size={22} className="text-muted-foreground/40" />
              <p className="text-sm font-medium text-muted-foreground">All clear</p>
              <p className="text-xs text-muted-foreground/60">No notifications yet.</p>
            </div>
          ) : (
            <div className="rounded-xl border overflow-hidden divide-y bg-card">
              {recentNotifs.map((n) => (
                <button
                  key={n.id}
                  onClick={() => {
                    if (!n.read) markRead.mutate(n.id)
                  }}
                  className={cn(
                    "w-full flex items-start gap-3 px-3.5 py-3 text-left hover:bg-muted/30 transition-colors",
                    !n.read && "bg-blue-500/5"
                  )}
                >
                  {notifIcon(n.type)}
                  <div className="flex-1 min-w-0">
                    <p className={cn("text-sm leading-snug", !n.read && "font-medium")}>
                      {n.message}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                    </p>
                  </div>
                  {!n.read && (
                    <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-blue-500 shrink-0" />
                  )}
                </button>
              ))}
              {allNotifs.length > 5 && (
                <div className="flex items-center justify-center py-2.5 text-xs text-muted-foreground">
                  Showing 5 of {allNotifs.length} notifications
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
