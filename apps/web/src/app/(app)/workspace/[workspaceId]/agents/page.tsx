"use client"
import { use, useState, useRef, useEffect, KeyboardEvent } from "react"
import { useSearchParams } from "next/navigation"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { differenceInDays } from "date-fns"
import { useAgentStatus, useAgentActivityFeed } from "@/hooks/use-agent-activity"
import { useProposedActions, useApproveAction, useRejectAction } from "@/hooks/use-agent-runs"
import { useWorkspaceIntelligence } from "@/hooks/use-intelligence"
import {
  useHermesAgents, useDeleteAgent, useRunAgent, useHermesChat,
  useAgentTeams, useDeleteTeam,
  type Agent, type CustomAgent, type AgentTeam,
} from "@/hooks/use-hermes"
import { CreateTeamDialog } from "@/components/hermes/create-team-dialog"
import { AgentActivityFeed } from "@/components/agents/agent-activity-feed"
import { AgentMemoryBrowser } from "@/components/agents/agent-memory-browser"
import { AgentSettingsTab } from "@/components/hermes/agent-settings-tab"
import { CreateAgentDialog } from "@/components/hermes/create-agent-dialog"
import { EditAgentDialog } from "@/components/hermes/edit-agent-dialog"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { useAuthStore } from "@/store/auth"
import {
  Activity, BarChart3, CheckCircle, ClipboardList, Cpu, HeartPulse,
  XCircle, Database, Search, Settings2, Trash2, Plus, MessageCircle,
  Play, Paperclip, ArrowUp, Square, Loader2, Sparkles, RefreshCw,
  Bot, Pencil, Command, FolderOpen, CheckSquare, ChevronDown, ChevronRight,
  Zap, Users, Brain, Wrench,
} from "lucide-react"
import { MarkdownMessage } from "@/components/hermes/markdown-message"
import { StreamStatusBar, ActivityTimeline } from "@/components/hermes/chat-stream-status"
import type { StreamStatus } from "@/hooks/use-hermes"

type Tab = "chat" | "agents" | "teams" | "activity" | "actions" | "memory" | "settings"
const VALID_TABS: Tab[] = ["chat", "agents", "teams", "activity", "actions", "memory", "settings"]

// ── Colour palette per agent slug ──────────────────────────────────────────

function getAgentTone(seed: string) {
  const tones = [
    { orb: "from-blue-500/20 to-indigo-500/20",   dot: "bg-blue-500"   },
    { orb: "from-fuchsia-500/20 to-violet-500/20", dot: "bg-fuchsia-500" },
    { orb: "from-emerald-500/20 to-teal-500/20",   dot: "bg-emerald-500" },
    { orb: "from-amber-500/20 to-orange-500/20",   dot: "bg-amber-500"  },
  ]
  const i = Array.from(seed).reduce((s, c) => s + c.charCodeAt(0), 0) % tones.length
  return tones[i]
}

function AgentIcon({ agent, size = 18 }: { agent?: Agent | null; size?: number }) {
  if (!agent) return <Cpu size={size} />
  if (agent.slug.includes("ops"))     return <Search size={size} />
  if (agent.slug.includes("digest"))  return <ClipboardList size={size} />
  if (agent.slug.includes("product")) return <BarChart3 size={size} />
  if (agent.slug.includes("pulse"))   return <HeartPulse size={size} />
  return <Bot size={size} />
}

// ── Greeting helper ────────────────────────────────────────────────────────

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return "Good morning"
  if (h < 17) return "Good afternoon"
  return "Good evening"
}

// ── Stat card ──────────────────────────────────────────────────────────────

function StatCard({
  icon,
  title,
  items,
}: {
  icon: React.ReactNode
  title: string
  items: { label: string; value: number; tone?: string }[]
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/10 text-indigo-600">
          {icon}
        </div>
        <span className="text-sm font-semibold">{title}</span>
      </div>
      <div className="flex items-end gap-5">
        {items.map(it => (
          <div key={it.label} className="flex flex-col gap-0.5">
            <span className={cn("text-2xl font-bold tabular-nums", it.tone ?? "text-foreground")}>
              {it.value}
            </span>
            <span className="text-[11px] text-muted-foreground leading-none">{it.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── AI Insights strip ──────────────────────────────────────────────────────

function InsightsStrip({ signals }: { signals: string[] }) {
  if (!signals.length) return null
  return (
    <div className="mt-8 w-full max-w-3xl rounded-2xl border border-amber-500/30 bg-amber-500/10 px-5 py-3.5">
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-500">
        AI Insights
      </p>
      <ul className="space-y-0.5">
        {signals.map((s, i) => (
          <li key={s} className="text-[13px] leading-5 text-amber-200/90">
            {s}
          </li>
        ))}
      </ul>
    </div>
  )
}

// ── Hero landing (empty chat state) ────────────────────────────────────────

interface HeroProps {
  workspaceId: string
  userName: string
  input: string
  onInputChange: (v: string) => void
  onSend: () => void
  isStreaming: boolean
}

function HeroLanding({ workspaceId, userName, input, onInputChange, onSend, isStreaming }: HeroProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Tasks stats
  const { data: tasksRaw } = useQuery<unknown>({
    queryKey: ["tasks", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/tasks`).then(r => r.data),
    enabled: !!workspaceId,
    staleTime: 60_000,
  })
  // Projects stats
  const { data: projectsRaw } = useQuery<unknown>({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/projects`).then(r => r.data),
    enabled: !!workspaceId,
    staleTime: 60_000,
  })
  // Agent status (for pending actions / weekly runs)
  const { data: agentStatus } = useAgentStatus(workspaceId)

  const { data: intelligence } = useWorkspaceIntelligence(workspaceId)
  const suggestedPrompts = intelligence?.suggested_prompts ?? [
    "Summarize updates",
    "What's blocked?",
    "Draft status update",
    "Analyze workload",
  ]
  const healthScore = intelligence?.health_score
  const riskSignals = intelligence?.risk_signals ?? []

  const now = new Date()
  const taskList: Array<{ status: string; priority?: string; due_date?: string }> = (
    Array.isArray(tasksRaw) ? tasksRaw : ((tasksRaw as { tasks?: unknown[] })?.tasks ?? [])
  ) as Array<{ status: string; priority?: string; due_date?: string }>
  const projectList: Array<{ status?: string }> = (
    Array.isArray(projectsRaw) ? projectsRaw : ((projectsRaw as { projects?: unknown[] })?.projects ?? [])
  ) as Array<{ status?: string }>

  const openTasks = taskList.filter(t => t.status !== "done" && t.status !== "cancelled")
  const overdueTasks = openTasks.filter(t => t.due_date && new Date(t.due_date) < now).length
  const weekTasks = openTasks.filter(t => t.due_date && differenceInDays(new Date(t.due_date), now) <= 7 && differenceInDays(new Date(t.due_date), now) >= 0).length
  const urgentTasks = openTasks.filter(t => t.priority === "urgent" || t.priority === "high").length

  const activeProjects = projectList.filter(p => p.status === "active").length
  const atRiskProjects = projectList.filter(p => p.status === "at_risk").length

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="flex flex-col items-center px-4 pb-12 pt-14">
      {/* Greeting */}
      <h1 className="text-4xl font-bold tracking-tight text-foreground">
        {greeting()}, {userName.split(" ")[0]}.
      </h1>
      <div className="mt-3 flex items-center justify-center gap-3">
        <p className="text-base text-muted-foreground">
          How can I help you with your work today?
        </p>
        {healthScore !== undefined && (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
              healthScore >= 80
                ? "bg-emerald-500/15 text-emerald-400"
                : healthScore >= 50
                ? "bg-amber-500/15 text-amber-400"
                : "bg-red-500/15 text-red-400"
            )}
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                healthScore >= 80
                  ? "bg-emerald-500"
                  : healthScore >= 50
                  ? "bg-amber-500"
                  : "bg-red-500"
              )}
            />
            Workspace {healthScore}/100
          </span>
        )}
      </div>

      {/* Chat input */}
      <div className="mt-9 w-full max-w-2xl rounded-2xl border border-border/70 bg-card shadow-sm">
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          placeholder="Ask anything about your workspace..."
          className="w-full resize-none bg-transparent px-5 pt-4 pb-2 text-base outline-none placeholder:text-muted-foreground/60"
          onChange={e => {
            onInputChange(e.target.value)
            e.target.style.height = "auto"
            e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`
          }}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
        />
        <div className="flex items-center justify-between px-4 pb-3">
          <Button variant="ghost" size="sm" className="h-8 w-8 rounded-xl p-0 text-muted-foreground hover:text-foreground">
            <Paperclip size={16} />
          </Button>
          <Button
            size="icon"
            className={cn(
              "h-9 w-9 rounded-xl transition-all",
              input.trim()
                ? "bg-indigo-600 text-white hover:bg-indigo-700"
                : "bg-muted text-muted-foreground"
            )}
            onClick={() => onSend()}
            disabled={!input.trim() || isStreaming}
          >
            {isStreaming ? <Loader2 size={15} className="animate-spin" /> : <ArrowUp size={15} />}
          </Button>
        </div>
      </div>

      {/* Quick prompt chips */}
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {suggestedPrompts.map(chip => (
          <button
            key={chip}
            onClick={() => onInputChange(chip)}
            className="rounded-full border border-border/60 bg-card px-4 py-1.5 text-sm text-foreground shadow-sm transition-colors hover:border-indigo-200 hover:bg-accent hover:text-indigo-700"
          >
            {chip}
          </button>
        ))}
      </div>

      <InsightsStrip signals={riskSignals} />

      {/* Stat cards */}
      <div className="mt-6 grid w-full max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          icon={<CheckSquare size={16} />}
          title="Tasks"
          items={[
            { label: "Urgent", value: urgentTasks, tone: "text-red-600" },
            { label: "Overdue", value: overdueTasks, tone: "text-orange-500" },
            { label: "This week", value: weekTasks },
          ]}
        />
        <StatCard
          icon={<FolderOpen size={16} />}
          title="Projects"
          items={[
            { label: "At risk", value: atRiskProjects, tone: "text-red-600" },
            { label: "Active", value: activeProjects },
            { label: "Total", value: projectList.length },
          ]}
        />
        <StatCard
          icon={<Sparkles size={16} />}
          title="AI Activity"
          items={[
            { label: "Runs / wk", value: agentStatus?.weekly_runs ?? 0 },
            { label: "Pending", value: agentStatus?.pending_actions ?? 0, tone: agentStatus?.pending_actions ? "text-amber-600" : undefined },
          ]}
        />
      </div>
    </div>
  )
}

// ── Tool-calls block (collapsible) ─────────────────────────────────────────

function ToolCallsBlock({
  tools,
  defaultOpen = false,
}: {
  tools: NonNullable<import("@/hooks/use-hermes").ChatMessage["toolCalls"]>
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  useEffect(() => {
    if (defaultOpen) setOpen(true)
  }, [defaultOpen, tools.length])
  if (tools.length === 0) return null
  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span className="font-medium">
          {tools.length} tool call{tools.length > 1 ? "s" : ""}
        </span>
        <span className="ml-1 text-muted-foreground/60">
          {tools.map(t => t.name).join(", ")}
        </span>
      </button>
      {open && (
        <div className="mt-1.5 rounded-xl border border-border/40 bg-muted/30 px-3 py-2 space-y-1">
          {tools.map((t, i) => (
            <div key={i} className="flex flex-col gap-0.5 text-xs">
              <div className="flex items-center gap-2">
                <Wrench size={11} className="text-amber-600 shrink-0" />
                <span className="font-mono text-foreground/80">{t.name}</span>
                {t.duration && (
                  <span className="ml-auto text-muted-foreground/60">{t.duration}</span>
                )}
              </div>
              {t.detail && (
                <span className="pl-5 text-muted-foreground/70 truncate">{t.detail}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Thinking animation ──────────────────────────────────────────────────────

function ThinkingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce"
          style={{ animationDelay: `${i * 160}ms`, animationDuration: "900ms" }}
        />
      ))}
    </span>
  )
}

// ── Full chat view ──────────────────────────────────────────────────────────

const CHAT_QUICK_PROMPTS = [
  "Summarize what's blocked across projects",
  "Run a team standup from memory",
  "List overdue tasks and suggest owners",
  "Draft a leadership status update",
]

interface FullChatProps {
  messages: import("@/hooks/use-hermes").ChatMessage[]
  input: string
  onInputChange: (v: string) => void
  onSend: () => void
  onStop: () => void
  onClear: () => void
  isStreaming: boolean
  streamStatus: StreamStatus | null
  agentName: string
  chatAgent: Agent | null
  agents: Agent[]
  onSelectAgent: (agent: Agent | null) => void
  onQuickPrompt: (text: string) => void
  suggestedPrompts?: string[]
}

function FullChat({
  messages,
  input,
  onInputChange,
  onSend,
  onStop,
  onClear,
  isStreaming,
  streamStatus,
  agentName,
  chatAgent,
  agents,
  onSelectAgent,
  onQuickPrompt,
  suggestedPrompts,
}: FullChatProps) {
  const displayPrompts = suggestedPrompts?.length
    ? suggestedPrompts
    : CHAT_QUICK_PROMPTS
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* ── Messages ─────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 pb-52 pt-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          {messages.map((msg, idx) => {
            const isLastHermes = msg.role === "hermes" && idx === messages.length - 1

            return (
              <div key={msg.id} className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}>

                {/* AI avatar */}
                {msg.role === "hermes" && (
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-border/70 bg-gradient-to-br from-indigo-500/20 to-blue-400/15 shadow-sm">
                    <Sparkles size={14} className="text-indigo-600" />
                  </div>
                )}

                {/* Bubble content */}
                <div className={cn("flex min-w-0 max-w-[min(82vw,46rem)] flex-col gap-0.5", msg.role === "user" ? "items-end" : "items-start")}>

                  {/* Role label */}
                  <div className="mb-1 px-1 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground/70">
                    {msg.role === "user" ? "You" : agentName}
                  </div>

                  {/* User bubble */}
                  {msg.role === "user" && (
                    <div className="rounded-[20px] rounded-br-md bg-foreground px-4 py-3 text-[15px] leading-7 text-background shadow-sm">
                      {msg.content}
                    </div>
                  )}

                  {/* AI bubble */}
                  {msg.role === "hermes" && (
                    <div className="w-full rounded-[20px] rounded-tl-md border border-border/50 bg-card px-5 py-4 shadow-sm">

                      {(msg.activitySteps?.length ?? 0) > 0 || (isLastHermes && isStreaming) ? (
                        <ActivityTimeline
                          steps={msg.activitySteps ?? []}
                          isLive={isLastHermes && isStreaming}
                        />
                      ) : null}

                      {msg.toolCalls && msg.toolCalls.length > 0 && (
                        <ToolCallsBlock
                          tools={msg.toolCalls}
                          defaultOpen={isLastHermes && isStreaming}
                        />
                      )}

                      {msg.content ? (
                        <MarkdownMessage content={msg.content} className="text-[15px] text-foreground" />
                      ) : isLastHermes && isStreaming ? (
                        <ThinkingDots />
                      ) : isLastHermes ? (
                        <p className="text-sm text-muted-foreground">
                          No response was received. Try again or use Stop if the request is still running.
                        </p>
                      ) : null}

                      {/* Streaming cursor */}
                      {isLastHermes && isStreaming && msg.content && (
                        <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse rounded-full bg-indigo-500 align-text-bottom" />
                      )}
                    </div>
                  )}
                </div>

                {/* User avatar */}
                {msg.role === "user" && (
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-foreground text-[11px] font-semibold text-background shadow-sm">
                    You
                  </div>
                )}
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Composer (Claude-style) ───────────────────────── */}
      <div className="shrink-0 px-4 pb-6">
        <div className="mx-auto max-w-3xl space-y-2">
          <StreamStatusBar status={streamStatus} />

          <div className="rounded-2xl border border-border/60 bg-card shadow-[0_8px_30px_rgba(15,23,42,0.08)]">
            <div className="flex items-center justify-between gap-2 border-b border-border/30 px-4 py-2">
              <div className="flex items-center gap-2 min-w-0">
                <Sparkles size={14} className="shrink-0 text-indigo-600" />
                <span className="truncate text-sm font-medium text-foreground">{agentName}</span>
                <span className="hidden sm:inline text-[11px] text-muted-foreground">· Hermes + workspace tools</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClear}
                className="h-7 shrink-0 gap-1 rounded-full px-2 text-[11px] text-muted-foreground hover:text-foreground"
              >
                <RefreshCw size={10} />
                New chat
              </Button>
            </div>

            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              placeholder={`Message ${agentName}…`}
              className="w-full min-h-[52px] resize-none bg-transparent px-4 py-3 text-[15px] outline-none placeholder:text-muted-foreground/50"
              onChange={e => {
                onInputChange(e.target.value)
                e.target.style.height = "auto"
                e.target.style.height = `${Math.min(e.target.scrollHeight, 220)}px`
              }}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
            />

            <div className="flex flex-wrap items-center gap-1.5 border-t border-border/30 px-3 py-2">
              <select
                value={chatAgent?.id ?? ""}
                onChange={e => {
                  const id = e.target.value
                  if (!id) {
                    onSelectAgent(null)
                    return
                  }
                  const found = agents.find(a => a.id === id)
                  onSelectAgent(found ?? null)
                }}
                disabled={isStreaming}
                className="h-8 max-w-[140px] truncate rounded-full border border-border/60 bg-muted px-2.5 text-xs text-foreground outline-none focus:border-indigo-400"
                title="Route to a specific agent personality"
              >
                <option value="">Default assistant</option>
                {agents.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.builtin ? "★ " : ""}{a.name}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled
                title="File attachments coming soon"
                className="h-8 gap-1 rounded-full px-2.5 text-xs text-muted-foreground"
              >
                <Paperclip size={12} />
                Attach
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={isStreaming}
                className="h-8 gap-1 rounded-full px-2.5 text-xs"
                onClick={() => onQuickPrompt("Search workspace memory for recent decisions and blockers.")}
              >
                <Brain size={12} />
                Memory
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={isStreaming}
                className="h-8 gap-1 rounded-full px-2.5 text-xs"
                onClick={() => onQuickPrompt("List proposed actions awaiting approval and summarize each.")}
              >
                <Zap size={12} />
                Actions
              </Button>
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-border/30 px-4 py-2.5">
              <span className="flex items-center gap-1 text-[11px] text-muted-foreground/60">
                <Command size={10} />
                Enter to send · Shift+Enter newline
              </span>
              {isStreaming ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-9 gap-1.5 rounded-xl border-red-500/30 bg-red-500/10 px-4 text-xs font-medium text-red-400 hover:bg-red-500/20"
                  onClick={onStop}
                >
                  <Square size={12} />
                  Stop generating
                </Button>
              ) : (
                <Button
                  size="sm"
                  className={cn(
                    "h-9 gap-1.5 rounded-xl px-4 text-xs font-medium transition-all",
                    input.trim()
                      ? "bg-indigo-600 text-white shadow-sm hover:bg-indigo-700"
                      : "bg-muted text-muted-foreground"
                  )}
                  onClick={() => onSend()}
                  disabled={!input.trim()}
                >
                  <ArrowUp size={14} />
                  Send
                </Button>
              )}
            </div>
          </div>

          {!isStreaming && (
            <div className="flex flex-wrap gap-2 px-1">
              {displayPrompts.map(prompt => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => onQuickPrompt(prompt)}
                  className="rounded-full border border-border/60 bg-card px-3 py-1.5 text-xs text-muted-foreground shadow-sm transition-colors hover:border-indigo-200 hover:bg-accent/50 hover:text-indigo-800"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Agent card ─────────────────────────────────────────────────────────────

function AgentCard({
  agent,
  isActive,
  onChat,
  onEdit,
  onRun,
  onDelete,
  runPending,
}: {
  agent: Agent
  isActive: boolean
  onChat: () => void
  onEdit?: () => void
  onRun?: () => void
  onDelete?: () => void
  runPending?: boolean
}) {
  const isCustom = !agent.builtin
  const lastRunAt = isCustom ? (agent as CustomAgent).last_run_at : null
  const runCount  = isCustom ? (agent as CustomAgent).run_count   : null
  const tone = getAgentTone(agent.slug)

  return (
    <div className="rounded-[22px] border border-border/80 bg-card/90 p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className={cn("flex h-11 w-11 items-center justify-center rounded-2xl border", `border-border/70 bg-gradient-to-br ${tone.orb}`)}>
            <AgentIcon agent={agent} />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <p className="font-medium text-sm">{agent.name}</p>
              {isActive && <span className={cn("h-1.5 w-1.5 rounded-full animate-pulse", tone.dot)} />}
            </div>
            <p className="mt-0.5 text-[11px] text-muted-foreground">{agent.schedule ?? "Manual"}</p>
          </div>
        </div>
        <div className="flex gap-1 shrink-0">
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={onChat} title="Chat">
            <MessageCircle size={13} />
          </Button>
          {onEdit && (
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={onEdit} title="Edit">
              <Pencil size={13} />
            </Button>
          )}
          {onRun && (
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={onRun} disabled={runPending} title="Run now">
              <Play size={13} />
            </Button>
          )}
          {onDelete && (
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-destructive hover:text-destructive" onClick={onDelete} title="Delete">
              <Trash2 size={13} />
            </Button>
          )}
        </div>
      </div>

      {agent.description && (
        <p className="mt-3 text-xs leading-5 text-muted-foreground line-clamp-2">{agent.description}</p>
      )}

      {lastRunAt && (
        <p className="mt-2 text-[10px] text-muted-foreground">
          Last run: {new Date(lastRunAt).toLocaleString()} · {runCount} total
        </p>
      )}
    </div>
  )
}

// ── Team card ──────────────────────────────────────────────────────────────

function TeamCard({
  team,
  allAgents,
  onDelete,
  onUpdate,
  onAddMember,
  onRemoveMember,
  onChatWithCoordinator,
}: {
  team: AgentTeam
  allAgents: CustomAgent[]
  onDelete: (teamId: string) => void
  onUpdate: (teamId: string, updates: { name?: string; goal?: string }) => void
  onAddMember: (teamId: string, agentId: string, teamRole: "coordinator" | "specialist") => void
  onRemoveMember: (teamId: string, agentId: string) => void
  onChatWithCoordinator: (prompt: string) => void
}) {
  const coordinator = team.members.find((m) => m.team_role === "coordinator")
  const specialists = team.members.filter((m) => m.team_role === "specialist")

  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState(team.name)
  const [editGoal, setEditGoal] = useState(team.goal ?? "")

  const [showAddMember, setShowAddMember] = useState(false)
  const [addAgentId, setAddAgentId] = useState("")
  const [addRole, setAddRole] = useState<"coordinator" | "specialist">("specialist")

  const memberAgentIds = new Set(team.members.map((m) => m.agent_id))
  const availableAgents = allAgents.filter((a) => !memberAgentIds.has(a.id))

  function handleSaveEdit() {
    onUpdate(team.id, { name: editName.trim() || team.name, goal: editGoal.trim() })
    setIsEditing(false)
  }

  function handleCancelEdit() {
    setEditName(team.name)
    setEditGoal(team.goal ?? "")
    setIsEditing(false)
  }

  function handleConfirmAddMember() {
    if (!addAgentId) return
    onAddMember(team.id, addAgentId, addRole)
    setAddAgentId("")
    setAddRole("specialist")
    setShowAddMember(false)
  }

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        {isEditing ? (
          <div className="flex-1 space-y-1.5">
            <input
              className="w-full rounded-md border border-border/70 bg-background px-2 py-1 text-sm font-medium outline-none focus:border-indigo-400"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="Team name"
            />
            <input
              className="w-full rounded-md border border-border/70 bg-background px-2 py-1 text-xs text-muted-foreground outline-none focus:border-indigo-400"
              value={editGoal}
              onChange={(e) => setEditGoal(e.target.value)}
              placeholder="Team goal (optional)"
            />
            <div className="flex gap-1.5 pt-0.5">
              <Button
                size="sm"
                className="h-6 px-2 text-[11px] bg-indigo-600 text-white hover:bg-indigo-700"
                onClick={handleSaveEdit}
              >
                Save
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-[11px]"
                onClick={handleCancelEdit}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <h3 className="font-medium text-sm truncate">{team.name}</h3>
              <button
                className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setIsEditing(true)}
                title="Edit team"
              >
                <Pencil size={11} />
              </button>
            </div>
            {team.goal && (
              <p className="text-xs text-muted-foreground mt-0.5 truncate">{team.goal}</p>
            )}
          </div>
        )}
        {!isEditing && (
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 h-6 w-6 text-muted-foreground hover:text-destructive"
            onClick={() => onDelete(team.id)}
          >
            <Trash2 size={12} />
          </Button>
        )}
      </div>

      {/* Members */}
      <div className="space-y-1">
        {coordinator && (
          <div className="flex items-center justify-between gap-1 text-xs text-muted-foreground">
            <span>
              <span className="font-medium text-foreground">👑 Coordinator:</span>{" "}
              {coordinator.avatar_emoji} {coordinator.agent_name}
            </span>
            <button
              className="shrink-0 rounded p-0.5 text-muted-foreground/60 hover:text-destructive transition-colors"
              onClick={() => onRemoveMember(team.id, coordinator.agent_id)}
              title="Remove coordinator"
            >
              <XCircle size={12} />
            </button>
          </div>
        )}
        {specialists.length > 0 && (
          <div className="space-y-1">
            <span className="text-xs font-medium text-foreground">Specialists:</span>
            {specialists.map((s) => (
              <div key={s.agent_id} className="flex items-center justify-between gap-1 text-xs text-muted-foreground pl-2">
                <span>{s.avatar_emoji} {s.agent_name}</span>
                <button
                  className="shrink-0 rounded p-0.5 text-muted-foreground/60 hover:text-destructive transition-colors"
                  onClick={() => onRemoveMember(team.id, s.agent_id)}
                  title="Remove specialist"
                >
                  <XCircle size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Add member inline form */}
        {showAddMember ? (
          <div className="mt-2 rounded-lg border border-border/60 bg-muted/40 p-2 space-y-2">
            <select
              className="w-full rounded-md border border-border/70 bg-background px-2 py-1 text-xs outline-none focus:border-indigo-400"
              value={addAgentId}
              onChange={(e) => setAddAgentId(e.target.value)}
            >
              <option value="">Select agent…</option>
              {availableAgents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.avatar_emoji} {a.name}
                </option>
              ))}
            </select>
            <div className="flex items-center gap-3 text-xs">
              <label className="flex items-center gap-1 cursor-pointer">
                <input
                  type="radio"
                  name={`role-${team.id}`}
                  value="specialist"
                  checked={addRole === "specialist"}
                  onChange={() => setAddRole("specialist")}
                  className="accent-indigo-600"
                />
                Specialist
              </label>
              <label className="flex items-center gap-1 cursor-pointer">
                <input
                  type="radio"
                  name={`role-${team.id}`}
                  value="coordinator"
                  checked={addRole === "coordinator"}
                  onChange={() => setAddRole("coordinator")}
                  className="accent-indigo-600"
                />
                Coordinator
              </label>
            </div>
            <div className="flex gap-1.5">
              <Button
                size="sm"
                className="h-6 px-2 text-[11px] bg-indigo-600 text-white hover:bg-indigo-700"
                onClick={handleConfirmAddMember}
                disabled={!addAgentId}
              >
                Add
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-[11px]"
                onClick={() => { setShowAddMember(false); setAddAgentId(""); setAddRole("specialist") }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          availableAgents.length > 0 && (
            <button
              className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground hover:text-indigo-600 transition-colors"
              onClick={() => setShowAddMember(true)}
            >
              <Plus size={11} />
              Add member
            </button>
          )
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {coordinator && (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => {
              const prompt = `[Team: ${team.name}] You are the coordinator of this team. Run the morning team standup: read team.report.* memory keys, summarize what each specialist did, assign today's handoffs.`
              onChatWithCoordinator(prompt)
            }}
          >
            Chat with team
          </Button>
        )}
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function AgentsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = use(params)
  const searchParams = useSearchParams()
  const tabParam = searchParams.get("tab") as Tab | null

  const [activeTab, setActiveTab] = useState<Tab>(
    tabParam && VALID_TABS.includes(tabParam) ? tabParam : "chat"
  )
  const [chatAgent, setChatAgent] = useState<Agent | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [editAgent, setEditAgent] = useState<CustomAgent | null>(null)
  const [chatInput, setChatInput] = useState("")
  const [showCreateTeamDialog, setShowCreateTeamDialog] = useState(false)

  const user = useAuthStore(s => s.user)
  const qc = useQueryClient()

  // Data hooks
  const { data: statusData } = useAgentStatus(workspaceId)
  const { data: intelligence } = useWorkspaceIntelligence(workspaceId)
  const { events, clearEvents } = useAgentActivityFeed(workspaceId)
  const { data: actionsData } = useProposedActions(workspaceId)
  const { data: agentsData } = useHermesAgents(workspaceId)
  const { data: teamsData } = useAgentTeams(workspaceId)
  const deleteTeamMutation = useDeleteTeam(workspaceId)
  const approveMutation = useApproveAction(workspaceId)
  const rejectMutation  = useRejectAction(workspaceId)
  const deleteMutation  = useDeleteAgent(workspaceId)
  const runMutation     = useRunAgent(workspaceId)

  // Team management handlers
  async function handleUpdateTeam(teamId: string, updates: { name?: string; goal?: string }) {
    await api.put(`/workspaces/${workspaceId}/hermes/teams/${teamId}`, updates)
    qc.invalidateQueries({ queryKey: ["hermes-teams", workspaceId] })
  }

  async function handleAddMember(teamId: string, agentId: string, teamRole: "coordinator" | "specialist") {
    await api.post(`/workspaces/${workspaceId}/hermes/teams/${teamId}/members`, { agent_id: agentId, team_role: teamRole })
    qc.invalidateQueries({ queryKey: ["hermes-teams", workspaceId] })
  }

  async function handleRemoveMember(teamId: string, agentId: string) {
    await api.delete(`/workspaces/${workspaceId}/hermes/teams/${teamId}/members/${agentId}`)
    qc.invalidateQueries({ queryKey: ["hermes-teams", workspaceId] })
  }

  // Chat state (lifted up so Hero and FullChat can share it)
  const { messages, sendMessage, stopStreaming, clearMessages, isStreaming, streamStatus } =
    useHermesChat(workspaceId)

  const allAgents: Agent[] = [
    ...(agentsData?.builtin ?? []),
    ...(agentsData?.custom ?? []),
  ]
  const isAgentActive = events.length > 0

  function handleSend(text?: string) {
    const msg = (typeof text === "string" ? text : chatInput).trim()
    if (!msg || isStreaming) return
    setChatInput("")
    sendMessage(msg, chatAgent?.slug ?? undefined)
  }

  function handleQuickPrompt(text: string) {
    setChatInput(text)
    handleSend(text)
  }

  function openChat(agent: Agent) {
    setChatAgent(agent)
    setActiveTab("chat")
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: "chat",     label: "Chat",     icon: <Sparkles size={14} /> },
    { id: "agents",   label: "Agents",   icon: <Bot size={14} /> },
    { id: "teams",    label: "Teams",    icon: <Users size={14} /> },
    { id: "activity", label: "Live feed", icon: <Activity size={14} />, badge: events.length || undefined },
    { id: "memory",   label: "Memory",   icon: <Database size={14} /> },
    { id: "actions",  label: "Actions",  icon: <CheckCircle size={14} />, badge: statusData?.pending_actions || undefined },
    { id: "settings", label: "Settings", icon: <Settings2 size={14} /> },
  ]

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">

      {/* ── Top tab bar ─────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-border/60 bg-card/90 px-4 backdrop-blur-xl">
        <div className="flex items-center justify-between gap-4 py-2">
          <nav className="flex gap-0.5 overflow-x-auto">
            {tabs.map(({ id, label, icon, badge }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={cn(
                  "relative flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-medium whitespace-nowrap transition-colors",
                  activeTab === id
                    ? "bg-accent/10 text-indigo-700"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                {icon}
                {label}
                {badge != null && badge > 0 && (
                  <span className="ml-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-indigo-600 px-1 text-[10px] font-semibold text-white">
                    {badge}
                  </span>
                )}
              </button>
            ))}
          </nav>

          <Button
            size="sm"
            onClick={() => setShowCreateDialog(true)}
            className="shrink-0 h-8 rounded-lg bg-slate-950 text-white hover:bg-slate-900"
          >
            <Plus size={14} />
            New agent
          </Button>
        </div>
      </div>

      {/* ── Content area ────────────────────────────────────────── */}
      <div className="min-w-0 flex-1 overflow-auto">

        {/* Chat tab */}
        {activeTab === "chat" && (
          messages.length === 0 ? (
            <HeroLanding
              workspaceId={workspaceId}
              userName={user?.name ?? "there"}
              input={chatInput}
              onInputChange={setChatInput}
              onSend={() => handleSend()}
              isStreaming={isStreaming}
            />
          ) : (
            <div className="h-full">
              <FullChat
                messages={messages}
                input={chatInput}
                onInputChange={setChatInput}
                onSend={() => handleSend()}
                onStop={stopStreaming}
                onClear={() => { clearMessages(); setChatInput("") }}
                isStreaming={isStreaming}
                streamStatus={streamStatus}
                agentName={chatAgent?.name ?? "AI Assistant"}
                chatAgent={chatAgent}
                agents={allAgents}
                onSelectAgent={setChatAgent}
                onQuickPrompt={handleQuickPrompt}
                suggestedPrompts={intelligence?.suggested_prompts}
              />
            </div>
          )
        )}

        {/* Agents tab */}
        {activeTab === "agents" && (
          <div className="p-6 space-y-6 max-w-5xl">
            <div>
              <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">
                Built-in Automations
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {(agentsData?.builtin ?? []).map(agent => (
                  <AgentCard
                    key={agent.id}
                    agent={agent}
                    isActive={isAgentActive}
                    onChat={() => openChat(agent)}
                  />
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Custom Agents{agentsData?.custom.length ? ` (${agentsData.custom.length})` : ""}
                </h2>
              </div>
              {agentsData?.custom.length === 0 ? (
                <button
                  onClick={() => setShowCreateDialog(true)}
                  className="w-full border-2 border-dashed rounded-2xl p-10 text-center hover:border-indigo-300 hover:bg-accent/50 transition-colors"
                >
                  <Plus size={24} className="mx-auto mb-2 text-muted-foreground" />
                  <p className="text-sm font-medium">Create your first custom agent</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Give it a personality, a schedule, and its own model — or just ask Hermes to create one.
                  </p>
                </button>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {(agentsData?.custom ?? []).map(agent => (
                    <AgentCard
                      key={agent.id}
                      agent={agent}
                      isActive={isAgentActive}
                      onChat={() => openChat(agent)}
                      onEdit={() => setEditAgent(agent)}
                      onRun={() => runMutation.mutate(agent.id)}
                      onDelete={() => deleteMutation.mutate(agent.id)}
                      runPending={runMutation.isPending}
                    />
                  ))}
                </div>
              )}
            </div>

            {statusData && (
              <div className="grid grid-cols-3 gap-4 pt-2">
                {[
                  { label: "Total agents",       value: allAgents.length },
                  { label: "Runs this week",     value: statusData.weekly_runs },
                  { label: "Pending approvals",  value: statusData.pending_actions },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-2xl border bg-card p-4 text-center shadow-sm">
                    <p className="text-2xl font-bold">{value}</p>
                    <p className="text-xs text-muted-foreground mt-1">{label}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Teams tab */}
        {activeTab === "teams" && (
          <div className="p-6 space-y-4 max-w-5xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                Teams{(teamsData?.teams?.length ?? 0) > 0 ? ` (${teamsData!.teams.length})` : ""}
              </h2>
              <button
                type="button"
                className="flex items-center gap-1 text-sm border rounded px-2 py-1 hover:bg-muted transition-colors"
                onClick={() => setShowCreateTeamDialog(true)}
              >
                <Plus size={14} />
                New team
              </button>
            </div>
            {(teamsData?.teams ?? []).length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
                <Users size={32} className="mb-3 opacity-30" />
                <p className="text-sm">No teams yet</p>
                <p className="text-xs mt-1">Create a team to coordinate your agents</p>
                <button
                  type="button"
                  className="mt-4 flex items-center gap-1 text-sm border rounded px-3 py-1.5 hover:bg-muted"
                  onClick={() => setShowCreateTeamDialog(true)}
                >
                  <Plus size={14} /> Create first team
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {teamsData?.teams.map((team) => (
                  <TeamCard
                    key={team.id}
                    team={team}
                    allAgents={agentsData?.custom ?? []}
                    onDelete={(id) => deleteTeamMutation.mutate(id)}
                    onUpdate={handleUpdateTeam}
                    onAddMember={handleAddMember}
                    onRemoveMember={handleRemoveMember}
                    onChatWithCoordinator={(prompt) => {
                      setChatInput(prompt)
                      setActiveTab("chat")
                    }}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Activity tab */}
        {activeTab === "activity" && (
          <div className="p-6 max-w-3xl space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Live tool calls from the Hermes runtime and your agents.
              </p>
              {events.length > 0 && (
                <Button variant="ghost" size="sm" onClick={clearEvents}>
                  <Trash2 size={14} className="mr-1" /> Clear
                </Button>
              )}
            </div>
            <AgentActivityFeed events={events} />
          </div>
        )}

        {/* Actions tab */}
        {activeTab === "actions" && (
          <div className="p-6 max-w-3xl space-y-3">
            <p className="text-sm text-muted-foreground">
              Review AI-proposed actions before they change workspace data.
            </p>
            {(actionsData?.actions ?? []).length === 0 ? (
              <div className="flex flex-col items-center justify-center py-14 text-center text-muted-foreground">
                <CheckCircle size={24} className="mb-2 opacity-40" />
                <p className="text-sm">No pending actions</p>
                <p className="text-xs mt-1">Hermes routes approvals here when an automation needs confirmation.</p>
              </div>
            ) : (
              (actionsData?.actions ?? []).map(action => (
                <div key={action.id} className="rounded-xl border bg-card p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1 flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium capitalize">
                          {action.action_type.replace(/_/g, " ")}
                        </span>
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide",
                          action.risk_level === "high"   && "bg-red-500/15 text-red-400",
                          action.risk_level === "medium" && "bg-amber-500/15 text-amber-400",
                          action.risk_level === "low"    && "bg-green-500/15 text-green-400",
                        )}>
                          {action.risk_level}
                        </span>
                      </div>
                      <pre className="text-xs text-muted-foreground bg-muted rounded p-2 overflow-auto max-h-24">
                        {JSON.stringify(action.payload, null, 2)}
                      </pre>
                    </div>
                    {action.status === "pending" && (
                      <div className="flex gap-2 shrink-0">
                        <Button size="sm" onClick={() => approveMutation.mutate(action.id)} disabled={approveMutation.isPending}>
                          <CheckCircle size={14} className="mr-1" /> Approve
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => rejectMutation.mutate(action.id)} disabled={rejectMutation.isPending}>
                          <XCircle size={14} className="mr-1" /> Reject
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Memory tab */}
        {activeTab === "memory" && (
          <div className="p-6 max-w-3xl space-y-3">
            <p className="text-sm text-muted-foreground">
              Facts and observations accumulated about this workspace.
            </p>
            <AgentMemoryBrowser workspaceId={workspaceId} />
          </div>
        )}

        {/* Settings tab */}
        {activeTab === "settings" && <AgentSettingsTab workspaceId={workspaceId} />}
      </div>

      {/* ── Dialogs ─────────────────────────────────────────────── */}
      {showCreateDialog && (
        <CreateAgentDialog
          workspaceId={workspaceId}
          onClose={() => setShowCreateDialog(false)}
          onCreated={() => setShowCreateDialog(false)}
        />
      )}
      {editAgent && (
        <EditAgentDialog
          workspaceId={workspaceId}
          agent={editAgent}
          onClose={() => setEditAgent(null)}
          onSaved={() => setEditAgent(null)}
        />
      )}
      {showCreateTeamDialog && (
        <CreateTeamDialog
          workspaceId={workspaceId}
          onClose={() => setShowCreateTeamDialog(false)}
          onCreated={() => setShowCreateTeamDialog(false)}
        />
      )}
    </div>
  )
}
