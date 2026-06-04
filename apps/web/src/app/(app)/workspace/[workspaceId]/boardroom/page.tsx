"use client"
import { use, useState, useCallback, useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import {
  useBoardroomSessions,
  useCreateBoardroomSession,
  useBoardroomTools,
  useInterject,
  useStopSession,
  useApplyTasks,
  useBoardroomStream,
  type BoardroomSession,
  type BoardroomTurn,
  type BoardroomAgentDef,
  type BoardroomTool,
  type ToolEvent,
  type DebateMode,
  type SseEvent,
} from "@/hooks/use-boardroom"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  Plus, Play, Square, Send, ArrowLeft, CheckSquare,
  Loader2, Sparkles, ChevronRight, Minus,
  Wrench, ChevronDown, Globe, ListChecks, DollarSign, Calculator, FilePlus,
} from "lucide-react"

// ── Debate modes + tool presentation ───────────────────────────────────────

const DEBATE_MODES: { value: DebateMode; label: string; hint: string }[] = [
  { value: "round_robin", label: "Round-robin", hint: "Each agent speaks in turn, challenging the last" },
  { value: "structured",  label: "Structured",  hint: "Opening → rebuttal → cross-examination → closing" },
  { value: "dynamic",     label: "Dynamic",      hint: "A moderator sharpens the conflict each round" },
]

const TOOL_CATEGORY_LABEL: Record<string, string> = {
  research: "Research",
  workspace_read: "Workspace (read)",
  workspace_write: "Workspace (write)",
  calc: "Calculation",
}

function toolIcon(category: string, size = 12) {
  switch (category) {
    case "research": return <Globe size={size} />
    case "workspace_read": return <ListChecks size={size} />
    case "workspace_write": return <FilePlus size={size} />
    case "calc": return <Calculator size={size} />
    default: return <Wrench size={size} />
  }
}

function ToolEventChips({ events }: { events: ToolEvent[] }) {
  if (!events.length) return null
  return (
    <div className="flex flex-wrap gap-1.5 mb-2">
      {events.map((e, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 rounded-full bg-muted/70 border border-border/60 px-2 py-0.5 text-[10px] text-muted-foreground"
          title={e.summary}
        >
          <Wrench size={9} className="opacity-60" />
          <span className="font-medium text-foreground/80">{e.tool}</span>
          <span className="truncate max-w-[180px]">· {e.summary}</span>
        </span>
      ))}
    </div>
  )
}

// ── Agent identity palette ────────────────────────────────────────────────────

const AGENT_PALETTE = [
  { bg: "bg-violet-100 dark:bg-violet-900/30", text: "text-violet-700 dark:text-violet-300", dot: "bg-violet-500", glow: "shadow-violet-200 dark:shadow-violet-900", border: "border-violet-200 dark:border-violet-800" },
  { bg: "bg-sky-100 dark:bg-sky-900/30",    text: "text-sky-700 dark:text-sky-300",    dot: "bg-sky-500",    glow: "shadow-sky-200 dark:shadow-sky-900",    border: "border-sky-200 dark:border-sky-800" },
  { bg: "bg-emerald-100 dark:bg-emerald-900/30", text: "text-emerald-700 dark:text-emerald-300", dot: "bg-emerald-500", glow: "shadow-emerald-200", border: "border-emerald-200 dark:border-emerald-800" },
  { bg: "bg-amber-100 dark:bg-amber-900/30", text: "text-amber-700 dark:text-amber-300", dot: "bg-amber-500", glow: "shadow-amber-200", border: "border-amber-200 dark:border-amber-800" },
  { bg: "bg-rose-100 dark:bg-rose-900/30",  text: "text-rose-700 dark:text-rose-300",  dot: "bg-rose-500",  glow: "shadow-rose-200",   border: "border-rose-200 dark:border-rose-800" },
  { bg: "bg-teal-100 dark:bg-teal-900/30",  text: "text-teal-700 dark:text-teal-300",  dot: "bg-teal-500",  glow: "shadow-teal-200",   border: "border-teal-200 dark:border-teal-800" },
]

const PRIORITY_CONFIG: Record<string, { label: string; stripe: string; text: string }> = {
  low:    { label: "Low",    stripe: "bg-slate-400",  text: "text-slate-500" },
  medium: { label: "Medium", stripe: "bg-blue-400",   text: "text-blue-600" },
  high:   { label: "High",   stripe: "bg-amber-400",  text: "text-amber-600" },
  urgent: { label: "Urgent", stripe: "bg-red-500",    text: "text-red-600" },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function agentPalette(index: number) {
  return AGENT_PALETTE[index % AGENT_PALETTE.length]
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

function AgentAvatar({ emoji, index, size = "md", active = false }: {
  emoji: string
  index: number
  size?: "sm" | "md" | "lg"
  active?: boolean
}) {
  const p = agentPalette(index)
  const sizes = { sm: "w-7 h-7 text-sm", md: "w-9 h-9 text-base", lg: "w-11 h-11 text-xl" }
  return (
    <div className={cn(
      "rounded-full flex items-center justify-center shrink-0 transition-all duration-300",
      p.bg, sizes[size],
      active && "ring-2 ring-offset-1 ring-offset-background shadow-lg " + p.dot.replace("bg-", "ring-"),
    )}>
      <span className="leading-none select-none">{emoji}</span>
    </div>
  )
}

// Simple inline markdown: **bold**, newlines, bullet lists
function PlanText({ text }: { text: string }) {
  const lines = text.split("\n")
  return (
    <div className="space-y-1.5 text-sm leading-relaxed text-foreground">
      {lines.map((line, i) => {
        const t = line.trim()
        if (!t) return <div key={i} className="h-1.5" />
        if (t.startsWith("## ") || t.startsWith("### ")) {
          const heading = t.replace(/^#+\s*/, "").replace(/\*\*/g, "")
          return <p key={i} className="font-semibold text-foreground mt-3 first:mt-0">{heading}</p>
        }
        if (t.startsWith("* ") || t.startsWith("- ")) {
          return (
            <div key={i} className="flex gap-2.5 items-start pl-1">
              <span className="text-muted-foreground mt-1.5 text-[8px]">●</span>
              <span>{renderBold(t.slice(2))}</span>
            </div>
          )
        }
        return <p key={i}>{renderBold(t)}</p>
      })}
    </div>
  )
}

function renderBold(text: string) {
  const parts = text.split(/\*\*(.*?)\*\*/g)
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? <strong key={i} className="font-semibold">{p}</strong> : p
      )}
    </>
  )
}

// ── Default agents ─────────────────────────────────────────────────────────

const DEFAULT_BUILTIN_AGENTS: BoardroomAgentDef[] = [
  {
    name: "Ops Monitor",
    emoji: "🔍",
    persona_type: "builtin",
    system_prompt:
      "You are a skeptical operations lead who has watched projects fail due to overconfidence. You have strong opinions formed from experience: optimistic timelines are almost always wrong, vendor promises break at scale, and 'we'll fix it in production' is how companies burn money. When someone proposes something, your first instinct is: what breaks at 10x load? What is the true maintenance cost? Who owns this when it goes wrong at 2am? You will disagree loudly with anyone who underestimates operational complexity. Do not hedge. Do not list 'considerations'. Say what you actually believe and why others are wrong where they are.",
    turn_order: 0,
  },
  {
    name: "Product Manager",
    emoji: "📊",
    persona_type: "builtin",
    system_prompt:
      "You are a product manager who is impatient with over-engineering and deeply skeptical of building what can be bought. Your core belief: the fastest path to validated user value wins. You challenge teams to scope down, ship something, and learn before committing to building everything from scratch. When someone wants to build a complex internal system, you ask: do we have evidence users actually need this? What is the MVP? You will push back on anyone who conflates technical elegance with user value. Take a clear position on what should be built, bought, or dropped — don't just list tradeoffs.",
    turn_order: 1,
  },
]

// ── Setup form ────────────────────────────────────────────────────────────────

function SetupForm({ onStart, tools }: {
  onStart: (
    topic: string,
    rounds: number,
    debateMode: DebateMode,
    defaultTools: string[],
    agents: BoardroomAgentDef[],
  ) => void
  tools: BoardroomTool[]
}) {
  const [topic, setTopic] = useState("")
  const [rounds, setRounds] = useState(2)
  const [debateMode, setDebateMode] = useState<DebateMode>("round_robin")
  const [defaultTools, setDefaultTools] = useState<Set<string>>(new Set())
  const [customizeAgent, setCustomizeAgent] = useState<number | null>(null)
  const [agents, setAgents] = useState<BoardroomAgentDef[]>(DEFAULT_BUILTIN_AGENTS)
  const [adhocName, setAdhocName] = useState("")
  const [adhocEmoji, setAdhocEmoji] = useState("🤖")
  const [adhocRole, setAdhocRole] = useState("")
  const [showAddAgent, setShowAddAgent] = useState(false)

  const toolsByCategory = tools.reduce<Record<string, BoardroomTool[]>>((acc, t) => {
    (acc[t.category] ??= []).push(t)
    return acc
  }, {})

  function toggleDefaultTool(name: string) {
    setDefaultTools((prev) => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }

  // Per-agent override: undefined = inherit session default; array = explicit set.
  function setAgentTools(idx: number, next: string[] | undefined) {
    setAgents((prev) => prev.map((a, i) => (i === idx ? { ...a, tools: next ?? null } : a)))
  }
  function toggleAgentTool(idx: number, name: string) {
    setAgents((prev) =>
      prev.map((a, i) => {
        if (i !== idx) return a
        const cur = new Set(a.tools ?? [])
        cur.has(name) ? cur.delete(name) : cur.add(name)
        return { ...a, tools: Array.from(cur) }
      })
    )
  }

  function addAdhoc() {
    if (!adhocName.trim() || !adhocRole.trim()) return
    setAgents((prev) => [...prev, {
      name: adhocName.trim(),
      emoji: adhocEmoji || "🤖",
      persona_type: "adhoc",
      system_prompt: `You are a ${adhocName.trim()}. ${adhocRole.trim()}\n\nYou have a distinct point of view shaped by this role. When others speak, find what you genuinely disagree with and say so by name. Do not perform balance or list pros and cons — take a position and defend it. If you change your mind, say explicitly what moved you. The goal is a real decision, not a complete analysis.`,
      turn_order: agents.length,
    }])
    setAdhocName(""); setAdhocEmoji("🤖"); setAdhocRole("")
    setShowAddAgent(false)
  }

  function removeAgent(idx: number) {
    setAgents((prev) => prev.filter((_, i) => i !== idx).map((a, i) => ({ ...a, turn_order: i })))
  }

  return (
    <div className="max-w-xl mx-auto p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 bg-primary/8 text-primary rounded-full px-3 py-1 text-xs font-medium mb-3">
          <Sparkles size={11} />
          New Session
        </div>
        <h2 className="text-xl font-semibold tracking-tight">Convene the Boardroom</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Agents will deliberate and produce an actionable plan.
        </p>
      </div>

      {/* Topic */}
      <div className="mb-6">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
          Topic
        </label>
        <textarea
          className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all placeholder:text-muted-foreground/50 leading-relaxed"
          rows={3}
          placeholder="e.g. Should we build our own PDOA stack or use a third-party provider?"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
        />
        <p className="text-[11px] text-muted-foreground/60 mt-1.5 text-right">{topic.length} chars</p>
      </div>

      {/* Rounds */}
      <div className="mb-6">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
          Rounds per agent
        </label>
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              onClick={() => setRounds(n)}
              className={cn(
                "w-10 h-10 rounded-xl text-sm font-semibold transition-all border",
                rounds === n
                  ? "bg-primary text-primary-foreground border-primary shadow-sm shadow-primary/20"
                  : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
              )}
            >
              {n}
            </button>
          ))}
          <span className="flex items-center text-xs text-muted-foreground ml-1">
            {rounds === 1 ? "Quick take" : rounds <= 2 ? "Standard" : rounds <= 3 ? "Deep dive" : "Exhaustive"}
          </span>
        </div>
      </div>

      {/* Debate mode */}
      <div className="mb-6">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
          Debate format
        </label>
        <div className="grid grid-cols-3 gap-2">
          {DEBATE_MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => setDebateMode(m.value)}
              className={cn(
                "rounded-xl border px-3 py-2.5 text-left transition-all",
                debateMode === m.value
                  ? "border-primary bg-primary/5 shadow-sm shadow-primary/10"
                  : "border-border hover:border-primary/40"
              )}
            >
              <p className={cn("text-xs font-semibold", debateMode === m.value ? "text-primary" : "text-foreground")}>
                {m.label}
              </p>
              <p className="text-[10px] text-muted-foreground leading-snug mt-0.5">{m.hint}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Tool kit (session default) */}
      {tools.length > 0 && (
        <div className="mb-6">
          <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            <Wrench size={11} /> Default tools
            <span className="font-normal normal-case tracking-normal text-[10px] text-muted-foreground/60">
              — available to every agent (override per-agent below)
            </span>
          </label>
          <div className="space-y-2.5">
            {Object.entries(toolsByCategory).map(([cat, list]) => (
              <div key={cat}>
                <p className="text-[10px] font-medium text-muted-foreground/70 mb-1 flex items-center gap-1">
                  {toolIcon(cat, 10)} {TOOL_CATEGORY_LABEL[cat] ?? cat}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {list.map((t) => {
                    const on = defaultTools.has(t.name)
                    return (
                      <button
                        key={t.name}
                        onClick={() => toggleDefaultTool(t.name)}
                        title={t.description}
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-all",
                          on
                            ? "border-primary bg-primary/8 text-primary font-medium"
                            : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
                        )}
                      >
                        {t.label}
                        {t.risk === "medium" && (
                          <span className="text-[8px] uppercase tracking-wide text-amber-600">write</span>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Agents */}
      <div className="mb-6">
        <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
          Panel ({agents.length} agents)
        </label>
        <div className="space-y-2">
          {agents.map((a, i) => {
            const p = agentPalette(i)
            const overrides = Array.isArray(a.tools)
            const effectiveCount = overrides ? a.tools!.length : defaultTools.size
            const expanded = customizeAgent === i
            return (
              <div key={`${a.name}-${i}`} className={cn("rounded-xl border transition-all", p.border, p.bg)}>
                <div className="flex items-center gap-3 px-3.5 py-2.5">
                  <AgentAvatar emoji={a.emoji} index={i} size="sm" />
                  <div className="flex-1 min-w-0">
                    <p className={cn("text-sm font-medium", p.text)}>{a.name}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {a.persona_type}
                      {tools.length > 0 && (
                        <> · {overrides ? `${effectiveCount} custom tools` : `inherits ${effectiveCount} tools`}</>
                      )}
                    </p>
                  </div>
                  {tools.length > 0 && (
                    <button
                      onClick={() => setCustomizeAgent(expanded ? null : i)}
                      className={cn(
                        "flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg transition-colors",
                        expanded ? "text-primary bg-primary/10" : "text-muted-foreground/60 hover:text-foreground hover:bg-muted/40"
                      )}
                    >
                      <Wrench size={11} />
                      <ChevronDown size={11} className={cn("transition-transform", expanded && "rotate-180")} />
                    </button>
                  )}
                  <button
                    onClick={() => removeAgent(i)}
                    className="text-muted-foreground/40 hover:text-destructive transition-colors p-1 rounded-lg hover:bg-destructive/10"
                  >
                    <Minus size={12} />
                  </button>
                </div>

                {expanded && (
                  <div className="px-3.5 pb-3 pt-1 border-t border-border/40 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-muted-foreground">
                        {overrides ? "Custom toolset for this agent" : "Inheriting the default toolset"}
                      </span>
                      <button
                        onClick={() => setAgentTools(i, overrides ? undefined : Array.from(defaultTools))}
                        className="text-[10px] text-primary hover:underline"
                      >
                        {overrides ? "Reset to default" : "Customize"}
                      </button>
                    </div>
                    {overrides && (
                      <div className="flex flex-wrap gap-1.5">
                        {tools.map((t) => {
                          const on = (a.tools ?? []).includes(t.name)
                          return (
                            <button
                              key={t.name}
                              onClick={() => toggleAgentTool(i, t.name)}
                              title={t.description}
                              className={cn(
                                "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] transition-all",
                                on
                                  ? "border-primary bg-primary/8 text-primary font-medium"
                                  : "border-border/70 text-muted-foreground hover:border-primary/40"
                              )}
                            >
                              {toolIcon(t.category, 9)} {t.label}
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Add agent toggle */}
        <button
          onClick={() => setShowAddAgent(!showAddAgent)}
          className="mt-3 w-full flex items-center justify-center gap-1.5 py-2.5 rounded-xl border border-dashed border-border text-xs text-muted-foreground hover:border-primary/40 hover:text-primary transition-all"
        >
          <Plus size={12} />
          Add custom agent
        </button>

        {showAddAgent && (
          <div className="mt-3 rounded-xl border border-border bg-muted/20 p-4 space-y-3">
            <div className="flex gap-2">
              <input
                className="w-11 rounded-lg border border-border bg-background px-2 py-2 text-sm text-center focus:outline-none focus:ring-1 focus:ring-primary/30"
                placeholder="🤖"
                value={adhocEmoji}
                onChange={(e) => setAdhocEmoji(e.target.value)}
                maxLength={2}
              />
              <input
                className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
                placeholder="Name (e.g. CFO, Devil's Advocate)"
                value={adhocName}
                onChange={(e) => setAdhocName(e.target.value)}
              />
            </div>
            <textarea
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-primary/30"
              rows={2}
              placeholder="Role description — what lens do they bring?"
              value={adhocRole}
              onChange={(e) => setAdhocRole(e.target.value)}
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={addAdhoc} disabled={!adhocName || !adhocRole} className="text-xs">
                Add to panel
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowAddAgent(false)} className="text-xs">
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Start */}
      <Button
        className="w-full h-11 font-semibold gap-2 rounded-xl"
        disabled={!topic.trim() || agents.length === 0}
        onClick={() => onStart(topic.trim(), rounds, debateMode, Array.from(defaultTools), agents)}
      >
        <Play size={15} />
        Convene Boardroom
      </Button>
    </div>
  )
}

// ── Discussion view ───────────────────────────────────────────────────────────

const PHASE_LABEL: Record<string, string> = {
  opening: "Opening statements",
  rebuttal: "Rebuttal",
  cross_examination: "Cross-examination",
  closing: "Closing arguments",
}

function DiscussionView({
  session, liveTurns, activeAgent, liveToolEvents, currentPhase, streamStatus, synthesisText, stopping, onInterject, onStop,
}: {
  session: BoardroomSession
  liveTurns: BoardroomTurn[]
  activeAgent: { name: string; emoji: string } | null
  liveToolEvents: ToolEvent[]
  currentPhase: string | null
  streamStatus: "idle" | "streaming" | "synthesizing"
  synthesisText: string
  stopping: boolean
  onInterject: (msg: string) => void
  onStop: () => void
}) {
  const [interjectText, setInterjectText] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)
  const allTurns = [...session.transcript, ...liveTurns]

  const agentIndexMap = Object.fromEntries(
    session.agents.map((a, i) => [a.id, i])
  )
  const agentIndexByName = Object.fromEntries(
    session.agents.map((a, i) => [a.name, i])
  )

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [allTurns.length, activeAgent, synthesisText])

  // The streamed brief ends with a TASKS_JSON: block — hide it from the live view.
  const synthesisPreview = synthesisText.split("TASKS_JSON:")[0].trim()

  function handleSend() {
    if (!interjectText.trim()) return
    onInterject(interjectText.trim())
    setInterjectText("")
  }

  const agentTurnCount = allTurns.filter(t => t.role === "agent").length
  const totalExpected = session.agents.length * session.rounds_config
  const progress = Math.min((agentTurnCount / totalExpected) * 100, 95)

  return (
    <div className="flex h-full min-h-0">
      {/* Sidebar */}
      <div className="w-48 shrink-0 border-r border-border/60 flex flex-col">
        {/* Topic */}
        <div className="p-4 border-b border-border/40">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">Topic</p>
          <p className="text-xs text-foreground leading-snug line-clamp-3">{session.topic}</p>
          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            <span className="inline-flex items-center gap-1 rounded-full bg-muted/70 px-2 py-0.5 text-[10px] text-muted-foreground capitalize">
              {(session.debate_mode ?? "round_robin").replace("_", "-")}
            </span>
            {currentPhase && PHASE_LABEL[currentPhase] && (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 text-primary px-2 py-0.5 text-[10px] font-medium">
                {PHASE_LABEL[currentPhase]}
              </span>
            )}
          </div>
        </div>

        {/* Agents */}
        <div className="p-3 flex-1 space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-1 mb-2">Panel</p>
          {session.agents.map((agent, i) => {
            const isActive = activeAgent?.name === agent.name
            const p = agentPalette(i)
            return (
              <div key={agent.id} className={cn(
                "flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs transition-all duration-300",
                isActive ? cn("font-medium shadow-sm", p.bg, p.text) : "text-muted-foreground hover:bg-muted/40"
              )}>
                <div className={cn("w-1.5 h-1.5 rounded-full shrink-0 transition-all", isActive ? cn(p.dot, "animate-pulse") : "bg-muted-foreground/20")} />
                <span className="truncate">{agent.emoji} {agent.name}</span>
                {isActive && <Loader2 size={10} className="ml-auto animate-spin shrink-0 opacity-70" />}
              </div>
            )
          })}
        </div>

        {/* Progress + status */}
        <div className="p-3 border-t border-border/40 space-y-3">
          {streamStatus === "synthesizing" ? (
            <div className="flex items-center gap-1.5 text-[11px] text-violet-600 font-medium px-1">
              <Sparkles size={11} className="animate-pulse" />
              Synthesizing…
            </div>
          ) : streamStatus === "streaming" ? (
            <div className="px-1">
              <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
                <span>Progress</span>
                <span>{agentTurnCount}/{totalExpected}</span>
              </div>
              <div className="h-1 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full transition-all duration-700" style={{ width: `${progress}%` }} />
              </div>
            </div>
          ) : null}

          <Button
            size="sm"
            variant="ghost"
            className="w-full h-7 text-xs text-muted-foreground"
            onClick={onStop}
            disabled={stopping || streamStatus === "synthesizing"}
            title="Stop the debate and produce the final report from the discussion so far"
          >
            {stopping || streamStatus === "synthesizing" ? (
              <><Loader2 size={10} className="mr-1.5 animate-spin" /> Finishing…</>
            ) : (
              <><Square size={10} className="mr-1.5" /> Stop & summarize</>
            )}
          </Button>
        </div>
      </div>

      {/* Main chat */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {allTurns.length === 0 && (
            <div className="flex flex-col items-center justify-center h-40 gap-3">
              <div className="flex -space-x-2">
                {session.agents.slice(0, 3).map((a, i) => (
                  <AgentAvatar key={a.id} emoji={a.emoji} index={i} size="md" />
                ))}
              </div>
              <p className="text-sm text-muted-foreground">Discussion starting…</p>
            </div>
          )}

          {allTurns.map((turn, i) => {
            if (turn.role === "moderator") {
              return (
                <div key={i} className="flex justify-center">
                  <div className="max-w-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl px-4 py-2.5 text-xs text-amber-800 dark:text-amber-200">
                    <span className="font-semibold mr-1.5">Moderator</span>
                    {turn.content}
                  </div>
                </div>
              )
            }

            const agentIndex = turn.agent_id ? (agentIndexMap[turn.agent_id] ?? agentIndexByName[turn.name] ?? 0) : agentIndexByName[turn.name] ?? 0
            const p = agentPalette(agentIndex)

            return (
              <div key={i} className="group">
                <div className="flex items-start gap-3">
                  <AgentAvatar emoji={turn.emoji ?? "🤖"} index={agentIndex} size="md" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={cn("text-xs font-semibold", p.text)}>{turn.name}</span>
                      {turn.round && (
                        <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded-full">
                          R{turn.round}
                        </span>
                      )}
                    </div>
                    <div className={cn("rounded-xl rounded-tl-sm border px-4 py-3", p.bg, p.border)}>
                      {turn.tool_events && turn.tool_events.length > 0 && (
                        <ToolEventChips events={turn.tool_events} />
                      )}
                      <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">
                        {turn.content}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}

          {/* Active agent thinking */}
          {activeAgent && (
            <div className="flex items-start gap-3">
              <AgentAvatar
                emoji={activeAgent.emoji}
                index={agentIndexByName[activeAgent.name] ?? 0}
                size="md"
                active
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={cn("text-xs font-semibold", agentPalette(agentIndexByName[activeAgent.name] ?? 0).text)}>
                    {activeAgent.name}
                  </span>
                  <span className="text-[10px] text-muted-foreground">thinking…</span>
                </div>
                <div className={cn("rounded-xl rounded-tl-sm border px-4 py-3.5", agentPalette(agentIndexByName[activeAgent.name] ?? 0).bg, agentPalette(agentIndexByName[activeAgent.name] ?? 0).border)}>
                  {liveToolEvents.length > 0 && <ToolEventChips events={liveToolEvents} />}
                  <div className="inline-flex items-center gap-1">
                    {[0, 1, 2].map((j) => (
                      <div
                        key={j}
                        className="w-1.5 h-1.5 rounded-full bg-current opacity-60 animate-bounce"
                        style={{ animationDelay: `${j * 150}ms`, animationDuration: "1s" }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {stopping && streamStatus !== "synthesizing" && (
            <div className="flex justify-center py-4">
              <div className="flex items-center gap-2.5 bg-muted/60 border border-border rounded-full px-5 py-2.5 text-xs text-muted-foreground font-medium">
                <Loader2 size={12} className="animate-spin" />
                Wrapping up — finishing the current turn, then summarizing…
              </div>
            </div>
          )}

          {streamStatus === "synthesizing" && (
            <div className="py-4 space-y-3">
              <div className="flex justify-center">
                <div className="flex items-center gap-2.5 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-full px-5 py-2.5 text-xs text-violet-700 dark:text-violet-300 font-medium">
                  <Sparkles size={12} className="animate-pulse" />
                  {synthesisPreview ? "Writing the final plan…" : "Synthesizing final plan…"}
                </div>
              </div>
              {synthesisPreview && (
                <div className="max-w-2xl mx-auto rounded-2xl border border-violet-200 dark:border-violet-800 bg-card p-6 shadow-sm">
                  <PlanText text={synthesisPreview} />
                </div>
              )}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Interject bar */}
        <div className="border-t border-border/60 p-4 bg-muted/20">
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 transition-all placeholder:text-muted-foreground/50"
              placeholder="Interject as moderator — steer the discussion…"
              value={interjectText}
              onChange={(e) => setInterjectText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            />
            <Button
              size="sm"
              className="px-4 rounded-xl h-full"
              onClick={handleSend}
              disabled={!interjectText.trim()}
            >
              <Send size={13} />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Output view ───────────────────────────────────────────────────────────────

function OutputView({ session, workspaceId, onViewTranscript }: {
  session: BoardroomSession
  workspaceId: string
  onViewTranscript: () => void
}) {
  const output = session.output!
  const applyAll = useApplyTasks(workspaceId, session.id)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [applied, setApplied] = useState(false)

  function toggleTask(i: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  function selectAll() {
    setSelected(new Set(output.proposed_tasks.map((_, i) => i)))
  }

  async function handleApply(ids: number[] | null) {
    await applyAll.mutateAsync(ids)
    setApplied(true)
  }

  const agentsByName = Object.fromEntries(session.agents.map((a, i) => [a.name, i]))

  return (
    <div className="max-w-2xl mx-auto p-8 space-y-7">

      {/* Status header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 rounded-full px-3 py-1 text-xs font-semibold mb-3">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Discussion complete
          </div>
          <h2 className="text-base font-semibold leading-snug text-foreground line-clamp-2">
            {session.topic}
          </h2>
          <div className="flex items-center gap-2 mt-2">
            <div className="flex -space-x-1.5">
              {session.agents.map((a, i) => (
                <AgentAvatar key={a.id} emoji={a.emoji} index={i} size="sm" />
              ))}
            </div>
            <span className="text-xs text-muted-foreground">
              {session.agents.length} agents · {session.rounds_config} rounds · {formatDate(session.created_at)}
            </span>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="text-xs shrink-0" onClick={onViewTranscript}>
          <ArrowLeft size={13} className="mr-1.5" /> Transcript
        </Button>
      </div>

      {/* Plan */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <div className="h-px flex-1 bg-border/60" />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground px-2">Action Plan</span>
          <div className="h-px flex-1 bg-border/60" />
        </div>
        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
          <PlanText text={output.plan} />
        </div>
      </div>

      {/* Tasks */}
      {output.proposed_tasks.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="h-px w-8 bg-border/60" />
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                {output.proposed_tasks.length} Proposed Tasks
              </span>
            </div>
            {selected.size < output.proposed_tasks.length && (
              <button onClick={selectAll} className="text-[11px] text-primary hover:underline">
                Select all
              </button>
            )}
          </div>

          <div className="space-y-2">
            {output.proposed_tasks.map((t, i) => {
              const prio = PRIORITY_CONFIG[t.priority] ?? PRIORITY_CONFIG.medium
              const isSelected = selected.has(i)
              return (
                <div
                  key={i}
                  onClick={() => toggleTask(i)}
                  className={cn(
                    "flex items-start gap-0 rounded-xl border overflow-hidden cursor-pointer transition-all duration-150 hover:shadow-sm",
                    isSelected ? "border-primary/40 shadow-sm shadow-primary/5" : "border-border hover:border-border-hover"
                  )}
                >
                  {/* Priority stripe */}
                  <div className={cn("w-1 self-stretch shrink-0", prio.stripe)} />

                  <div className="flex items-start gap-3 flex-1 px-4 py-3">
                    {/* Checkbox */}
                    <div className={cn(
                      "mt-0.5 w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 transition-all",
                      isSelected ? "bg-primary border-primary" : "border-muted-foreground/30"
                    )}>
                      {isSelected && <CheckSquare size={9} className="text-primary-foreground" />}
                    </div>

                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground">{t.title}</p>
                      {t.description && (
                        <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{t.description}</p>
                      )}
                    </div>

                    <span className={cn("text-[10px] font-semibold uppercase tracking-wider shrink-0 mt-0.5", prio.text)}>
                      {prio.label}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Apply */}
          <div className="mt-4">
            {applied ? (
              <div className="flex items-center gap-2 text-sm text-emerald-600 font-medium">
                <CheckSquare size={15} />
                {output.proposed_tasks.length} tasks created in workspace
              </div>
            ) : (
              <div className="flex gap-2">
                <Button
                  onClick={() => handleApply(null)}
                  disabled={applyAll.isPending}
                  className="gap-2 rounded-xl"
                >
                  {applyAll.isPending ? <Loader2 size={13} className="animate-spin" /> : <CheckSquare size={13} />}
                  Apply all {output.proposed_tasks.length} tasks
                </Button>
                {selected.size > 0 && (
                  <Button
                    variant="outline"
                    onClick={() => handleApply(Array.from(selected))}
                    disabled={applyAll.isPending}
                    className="rounded-xl"
                  >
                    Apply {selected.size} selected
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Session list ──────────────────────────────────────────────────────────────

function SessionList({ sessions, onSelect, onNew }: {
  sessions: BoardroomSession[]
  onSelect: (id: string) => void
  onNew: () => void
}) {
  const STATUS = {
    setup:        { label: "Setup",        dot: "bg-slate-400",   text: "text-slate-500" },
    running:      { label: "Running",      dot: "bg-blue-500 animate-pulse",    text: "text-blue-600" },
    paused:       { label: "Paused",       dot: "bg-amber-500",   text: "text-amber-600" },
    synthesizing: { label: "Synthesizing", dot: "bg-violet-500 animate-pulse",  text: "text-violet-600" },
    done:         { label: "Done",         dot: "bg-emerald-500", text: "text-emerald-600" },
  } as Record<string, { label: string; dot: string; text: string }>

  return (
    <div className="max-w-2xl mx-auto p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Boardroom</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Convene agents to deliberate and produce decisions.
          </p>
        </div>
        <Button onClick={onNew} className="gap-2 rounded-xl">
          <Plus size={15} /> New Session
        </Button>
      </div>

      {/* Empty state */}
      {sessions.length === 0 ? (
        <div className="border border-dashed border-border rounded-2xl py-16 flex flex-col items-center gap-4 text-center">
          <div className="flex -space-x-2 opacity-40">
            {["🔍", "📊", "🤖"].map((e, i) => (
              <div key={i} className={cn("w-10 h-10 rounded-full flex items-center justify-center text-lg", agentPalette(i).bg)}>
                {e}
              </div>
            ))}
          </div>
          <div>
            <p className="text-sm font-medium">No sessions yet</p>
            <p className="text-xs text-muted-foreground mt-1">Start a boardroom to get structured AI deliberation.</p>
          </div>
          <Button size="sm" onClick={onNew} variant="outline" className="rounded-xl gap-1.5">
            <Plus size={13} /> New Session
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => {
            const st = STATUS[s.status] ?? STATUS.setup
            return (
              <button
                key={s.id}
                onClick={() => onSelect(s.id)}
                className="w-full text-left px-5 py-4 rounded-2xl border border-border bg-card hover:bg-muted/30 hover:border-border/80 hover:shadow-sm transition-all duration-150 group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate group-hover:text-primary transition-colors">
                      {s.topic}
                    </p>
                    <div className="flex items-center gap-3 mt-1.5">
                      <div className="flex -space-x-1">
                        {s.agents.slice(0, 4).map((a, i) => (
                          <div key={a.id} className={cn("w-5 h-5 rounded-full flex items-center justify-center text-[10px] border border-background", agentPalette(i).bg)}>
                            {a.emoji}
                          </div>
                        ))}
                      </div>
                      <span className="text-[11px] text-muted-foreground">
                        {s.rounds_config}r · {formatDate(s.created_at)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <div className={cn("flex items-center gap-1.5 text-[11px] font-medium", st.text)}>
                      <div className={cn("w-1.5 h-1.5 rounded-full", st.dot)} />
                      {st.label}
                    </div>
                    <ChevronRight size={13} className="text-muted-foreground group-hover:text-foreground transition-colors" />
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

type View = "list" | "setup" | "session"

export default function BoardroomPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params)
  const qc = useQueryClient()
  const { data: sessions = [] } = useBoardroomSessions(workspaceId)
  const { data: tools = [] } = useBoardroomTools(workspaceId)
  const createSession = useCreateBoardroomSession(workspaceId)

  const [view, setView] = useState<View>("list")
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [showTranscript, setShowTranscript] = useState(false)
  const [liveTurns, setLiveTurns] = useState<BoardroomTurn[]>([])
  const [activeAgent, setActiveAgent] = useState<{ name: string; emoji: string } | null>(null)
  const [liveToolEvents, setLiveToolEvents] = useState<ToolEvent[]>([])
  const [currentPhase, setCurrentPhase] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const [streamStatus, setStreamStatus] = useState<"idle" | "streaming" | "synthesizing">("idle")
  const [synthesisText, setSynthesisText] = useState("")

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null

  const handleSseEvent = useCallback((event: SseEvent) => {
    if (event.type === "turn_start" && event.agent) {
      setActiveAgent({ name: event.agent.name, emoji: event.agent.emoji })
      setLiveToolEvents([])
      setStreamStatus("streaming")
    } else if (event.type === "tool_result" && event.tool) {
      setLiveToolEvents((prev) => [...prev, { tool: event.tool!, summary: event.summary ?? "" }])
    } else if (event.type === "phase_start" && event.phase) {
      setCurrentPhase(event.phase)
    } else if (event.type === "stopping") {
      setStopping(true)
      setActiveAgent(null)
    } else if (event.type === "turn_end" && event.agent_id && event.full_text) {
      const agent = activeSession?.agents.find((a) => a.id === event.agent_id)
      setLiveTurns((prev) => [...prev, {
        role: "agent", agent_id: event.agent_id,
        name: agent?.name ?? "Agent", emoji: agent?.emoji,
        content: event.full_text!,
        tool_events: event.tool_events,
      }])
      setActiveAgent(null)
      setLiveToolEvents([])
    } else if (event.type === "interject_ack" || event.type === "moderator_challenge") {
      setLiveTurns((prev) => [...prev, { role: "moderator", name: "Moderator", content: event.content ?? "" }])
    } else if (event.type === "synthesis_start") {
      setActiveAgent(null)
      setSynthesisText("")
      setStreamStatus("synthesizing")
    } else if (event.type === "synthesis_delta") {
      setSynthesisText((prev) => prev + (event.text ?? ""))
    } else if (event.type === "plan_ready") {
      setStreamStatus("idle")
      qc.invalidateQueries({ queryKey: ["boardroom-session", workspaceId, activeSessionId] })
      qc.invalidateQueries({ queryKey: ["boardroom-sessions", workspaceId] })
    }
  }, [activeSession, activeSessionId, workspaceId, qc])

  const handleStreamDone = useCallback(() => {
    setLiveTurns([]); setActiveAgent(null); setLiveToolEvents([]); setCurrentPhase(null)
    setStopping(false); setStreamStatus("idle"); setSynthesisText(""); setShowTranscript(false)
    qc.invalidateQueries({ queryKey: ["boardroom-session", workspaceId, activeSessionId] })
    qc.invalidateQueries({ queryKey: ["boardroom-sessions", workspaceId] })
  }, [workspaceId, activeSessionId, qc])

  const stream = useBoardroomStream({ workspaceId, sessionId: activeSessionId ?? "", onEvent: handleSseEvent, onDone: handleStreamDone })
  const interject = useInterject(workspaceId, activeSessionId ?? "")
  const stopSession = useStopSession(workspaceId, activeSessionId ?? "")

  async function handleStart(
    topic: string,
    rounds: number,
    debateMode: DebateMode,
    defaultTools: string[],
    agents: BoardroomAgentDef[],
  ) {
    const session = await createSession.mutateAsync({
      topic, rounds_config: rounds, debate_mode: debateMode, default_tools: defaultTools, agents,
    })
    setActiveSessionId(session.id); setLiveTurns([]); setLiveToolEvents([]); setCurrentPhase(null)
    setStopping(false); setShowTranscript(true); setView("session")
    void stream.start(session.id)
  }

  function handleSelectSession(id: string) {
    const session = sessions.find((s) => s.id === id)
    setActiveSessionId(id); setView("session")
    setShowTranscript(!session || session.status !== "done" || !session.output)
  }

  const showOutput = activeSession?.status === "done" && activeSession.output && !showTranscript
  const showDiscussion = view === "session" && activeSession && (showTranscript || activeSession.status !== "done")

  return (
    <div className="h-full flex flex-col">
      {/* Breadcrumb */}
      {view !== "list" && (
        <div className="border-b border-border/60 px-5 py-2.5 flex items-center gap-2.5 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
          <button
            onClick={() => { setView("list"); setActiveSessionId(null); setLiveTurns([]) }}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-lg hover:bg-muted/60"
          >
            <ArrowLeft size={15} />
          </button>
          <span className="text-xs text-muted-foreground">Boardroom</span>
          <ChevronRight size={11} className="text-muted-foreground/40" />
          <span className="text-xs text-foreground font-medium truncate max-w-xs">
            {view === "setup" ? "New session" : activeSession?.topic ?? "Session"}
          </span>
          {activeSession && (
            <div className="ml-auto">
              {activeSession.status === "running" && (
                <span className="text-[10px] font-medium text-blue-600 flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                  Live
                </span>
              )}
            </div>
          )}
        </div>
      )}

      <div className="flex-1 overflow-auto min-h-0">
        {view === "list" && <SessionList sessions={sessions} onSelect={handleSelectSession} onNew={() => setView("setup")} />}
        {view === "setup" && <SetupForm onStart={handleStart} tools={tools} />}
        {view === "session" && activeSession && showOutput && (
          <OutputView session={activeSession} workspaceId={workspaceId} onViewTranscript={() => setShowTranscript(true)} />
        )}
        {showDiscussion && (
          <div className="h-full">
            <DiscussionView
              session={activeSession!}
              liveTurns={liveTurns}
              activeAgent={activeAgent}
              liveToolEvents={liveToolEvents}
              currentPhase={currentPhase}
              streamStatus={streamStatus}
              synthesisText={synthesisText}
              stopping={stopping}
              onStop={() => { setStopping(true); stopSession.mutate() }}
              onInterject={(msg) => interject.mutate(msg)}
            />
          </div>
        )}
      </div>
    </div>
  )
}
