"use client"
import { use, useState, useRef, useEffect } from "react"
import {
  useAgentStatus, useRunDigest, useRunKnowledgeAgent,
  useMemories, useAddMemory, useDeleteMemory,
  type AgentInfo, type Memory,
} from "@/hooks/use-agents"
import { HermesChatPanel } from "@/components/hermes/hermes-chat-panel"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import { formatDistanceToNow } from "date-fns"
import {
  Sparkles, CheckSquare, FolderOpen, BookOpen,
  Calendar, Brain, Zap, Play, Loader2, Database,
  Trash2, Plus, X, Bot,
} from "lucide-react"

interface DisplayMessage extends ChatMessage {
  timestamp: Date
  agentType?: string
  actions?: Array<{ tool: string; result?: { ok?: boolean; error?: string } }>
}

const AGENT_ICONS: Record<string, React.ElementType> = {
  task:            CheckSquare,
  project_manager: FolderOpen,
  docs:            BookOpen,
  digest:          Calendar,
  knowledge:       Brain,
  chat:            Sparkles,
}

const AGENT_COLORS: Record<string, string> = {
  task:            "bg-blue-500/10 text-blue-500",
  project_manager: "bg-purple-500/10 text-purple-500",
  docs:            "bg-amber-500/10 text-amber-600",
  digest:          "bg-emerald-500/10 text-emerald-600",
  knowledge:       "bg-rose-500/10 text-rose-500",
  chat:            "bg-accent/10 text-accent",
}

const TRIGGER_BADGE: Record<string, string> = {
  auto:        "bg-emerald-500/10 text-emerald-600",
  "on-demand": "bg-blue-500/10 text-blue-500",
  scheduled:   "bg-amber-500/10 text-amber-600",
}

function ImportanceDots({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-0.5" title={`Importance: ${value}/5`}>
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            i < value ? "bg-accent" : "bg-muted-foreground/20"
          )}
        />
      ))}
    </span>
  )
}

function MemoryTab({ workspaceId }: { workspaceId: string }) {
  const { data, isPending } = useMemories(workspaceId)
  const { mutateAsync: addMemory, isPending: adding } = useAddMemory(workspaceId)
  const { mutate: deleteMemory } = useDeleteMemory(workspaceId)
  const [showForm, setShowForm] = useState(false)
  const [key, setKey] = useState("")
  const [content, setContent] = useState("")
  const [importance, setImportance] = useState(3)
  const memories = data?.memories ?? []

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!key.trim() || !content.trim()) return
    try {
      await addMemory({ key: key.trim(), content: content.trim(), importance })
      setKey("")
      setContent("")
      setImportance(3)
      setShowForm(false)
    } catch {/* ignore */}
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto space-y-4">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold">Workspace Memory</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Facts the AI learns from conversations — recalled in future queries.
            </p>
          </div>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
          >
            {showForm ? <X size={12} /> : <Plus size={12} />}
            {showForm ? "Cancel" : "Add memory"}
          </button>
        </div>

        {/* Add form */}
        {showForm && (
          <form onSubmit={handleAdd} className="rounded-xl border bg-card p-4 space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Key (dot notation)</label>
              <input
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="e.g. team.shaan.role"
                className="w-full text-sm bg-muted/40 rounded-lg px-3 py-2 outline-none focus:ring-1 focus:ring-accent/50 border border-transparent focus:border-accent/30"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Content</label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="What should the AI remember?"
                rows={2}
                className="w-full text-sm bg-muted/40 rounded-lg px-3 py-2 outline-none focus:ring-1 focus:ring-accent/50 border border-transparent focus:border-accent/30 resize-none"
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Importance:</span>
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setImportance(n)}
                    className={cn(
                      "h-5 w-5 rounded-full text-[10px] font-medium transition-colors",
                      importance === n
                        ? "bg-accent text-white"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    )}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <button
                type="submit"
                disabled={adding || !key.trim() || !content.trim()}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-accent text-white hover:bg-accent/90 disabled:opacity-50 transition-colors"
              >
                {adding ? <Loader2 size={11} className="animate-spin" /> : <Plus size={11} />}
                Save
              </button>
            </div>
          </form>
        )}

        {/* Memory list */}
        {isPending ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 size={20} className="animate-spin text-muted-foreground" />
          </div>
        ) : memories.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center">
            <Database size={28} className="text-muted-foreground/40 mb-3" />
            <p className="text-sm font-medium text-muted-foreground">No memories yet</p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              Chat with the AI — it will automatically extract and store useful facts.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {memories.map((m) => (
              <MemoryRow
                key={m.id}
                memory={m}
                onDelete={() => deleteMemory(m.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function MemoryRow({ memory, onDelete }: { memory: Memory; onDelete: () => void }) {
  return (
    <div className="group flex items-start gap-3 rounded-xl border bg-card px-4 py-3 hover:bg-muted/40 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <code className="text-[11px] font-mono text-accent/80 bg-accent/8 px-1.5 py-0.5 rounded">
            {memory.key}
          </code>
          <ImportanceDots value={memory.importance} />
          <span className={cn(
            "text-[9px] px-1.5 py-0.5 rounded-full font-medium uppercase tracking-wide",
            memory.source === "manual"
              ? "bg-blue-500/10 text-blue-500"
              : "bg-emerald-500/10 text-emerald-600"
          )}>
            {memory.source}
          </span>
        </div>
        <p className="text-xs text-foreground/80 mt-1.5 leading-relaxed">{memory.content}</p>
        {memory.updated_at && (
          <p className="text-[10px] text-muted-foreground/50 mt-1">
            {formatDistanceToNow(new Date(memory.updated_at), { addSuffix: true })}
          </p>
        )}
      </div>
      <button
        onClick={onDelete}
        className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all mt-0.5 shrink-0"
        title="Delete memory"
      >
        <Trash2 size={13} />
      </button>
    </div>
  )
}

function AgentCard({
  agent,
  workspaceId,
  onResult,
}: {
  agent: AgentInfo
  workspaceId: string
  onResult: (msg: string, agentType: string) => void
}) {
  const Icon = AGENT_ICONS[agent.type] ?? Sparkles
  const colorClass = AGENT_COLORS[agent.type] ?? "bg-muted text-muted-foreground"
  const { mutateAsync: runDigest, isPending: digestPending } = useRunDigest(workspaceId)
  const { isPending: knowledgePending } = useRunKnowledgeAgent(workspaceId)
  const isPending = digestPending || knowledgePending

  async function handleInvoke() {
    if (agent.type === "digest") {
      try {
        const res = await runDigest()
        onResult(res.content, "digest")
      } catch {
        onResult("Failed to generate digest. Check your API key.", "digest")
      }
    }
  }

  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-start gap-3 mb-3">
        <div className={cn("h-9 w-9 rounded-xl flex items-center justify-center shrink-0", colorClass)}>
          <Icon size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm capitalize">{agent.type.replace("_", " ")} Agent</span>
            <span className={cn("text-[10px] px-1.5 py-0.5 rounded-full font-medium capitalize", TRIGGER_BADGE[agent.trigger] ?? "bg-muted text-muted-foreground")}>
              {agent.trigger}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{agent.description}</p>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2">
        <code className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded truncate max-w-[160px]">
          {agent.model}
        </code>
        {agent.type === "digest" && (
          <button
            onClick={handleInvoke}
            disabled={isPending}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors disabled:opacity-50 shrink-0"
          >
            {isPending ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
            Run now
          </button>
        )}
        {agent.type === "knowledge" && (
          <span className="text-[10px] text-muted-foreground italic">Use @ai in channels</span>
        )}
        {agent.type === "task" && (
          <span className="text-[10px] text-muted-foreground italic">Runs on every message</span>
        )}
        {agent.type === "project_manager" && (
          <span className="text-[10px] text-muted-foreground italic">Use in Projects page</span>
        )}
        {agent.type === "docs" && (
          <span className="text-[10px] text-muted-foreground italic">Use in Doc editor</span>
        )}
      </div>
    </div>
  )
}

type Tab = "agents" | "chat" | "memory"

export default function AIHubPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = use(params)
  const { data: statusData } = useAgentStatus(workspaceId)
  const { data: memoriesData } = useMemories(workspaceId)
  const [activeTab, setActiveTab] = useState<Tab>("chat")

  const agents = statusData?.agents ?? []
  const memoryCount = memoriesData?.count ?? 0

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: "chat",   label: "Chat",   icon: Bot },
    { id: "agents", label: "Agents", icon: Zap },
    { id: "memory", label: "Memory", icon: Database },
  ]

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="h-14 border-b flex items-center gap-3 px-4 shrink-0">
        <span className="text-xl">🤖</span>
        <div>
          <p className="text-sm font-medium leading-none">Hermes</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Full workspace access · all tools enabled
          </p>
        </div>
        {/* Tab switcher */}
        <div className="ml-auto flex items-center bg-muted/60 rounded-lg p-0.5 gap-0.5">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={cn(
                "relative px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                activeTab === id
                  ? "bg-background shadow-sm text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="flex items-center gap-1.5">
                <Icon size={11} />
                {label}
                {id === "memory" && memoryCount > 0 && (
                  <span className="ml-0.5 text-[9px] bg-accent/20 text-accent rounded-full px-1.5 py-0.5 leading-none">
                    {memoryCount}
                  </span>
                )}
              </span>
            </button>
          ))}
        </div>
      </div>

      {activeTab === "agents" && (
        <div className="flex-1 overflow-y-auto p-6">
          {!statusData?.ai_enabled && (
            <div className="mb-4 p-4 rounded-xl border border-amber-500/30 bg-amber-500/5 text-sm text-amber-600 dark:text-amber-400">
              ⚠️ Set <code className="font-mono text-xs bg-amber-500/10 px-1 rounded">OPENROUTER_API_KEY</code> in your <code className="font-mono text-xs bg-amber-500/10 px-1 rounded">.env</code> to activate AI agents.
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {agents.map((agent) => (
              <AgentCard
                key={agent.type}
                agent={agent}
                workspaceId={workspaceId}
                onResult={() => setActiveTab("chat")}
              />
            ))}
          </div>
          {agents.length === 0 && (
            <div className="flex flex-col items-center justify-center h-48 text-center">
              <Loader2 size={20} className="animate-spin text-muted-foreground mb-3" />
              <p className="text-sm text-muted-foreground">Loading agents…</p>
            </div>
          )}
        </div>
      )}

      {activeTab === "chat" && (
        <HermesChatPanel workspaceId={workspaceId} className="flex-1 overflow-hidden" />
      )}

      {activeTab === "memory" && <MemoryTab workspaceId={workspaceId} />}
    </div>
  )
}
