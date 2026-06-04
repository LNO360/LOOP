"use client"
import { use, useState } from "react"
import { useMessages, useSendMessage, usePins, useUnpinMessage } from "@/hooks/use-messages"
import { useWorkspaceSocket } from "@/hooks/use-websocket"
import { MessageFeed } from "@/components/messaging/message-feed"
import { MessageComposer } from "@/components/messaging/message-composer"
import { ThreadPanel } from "@/components/messaging/thread-panel"
import { CreateTaskDialog } from "@/components/tasks/create-task-dialog"
import { useCreateTask } from "@/hooks/use-tasks"
import { useExtractTasks } from "@/hooks/use-ai"
import { useRunKnowledgeAgent, useRunDocsAgent } from "@/hooks/use-agents"
import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "@/store/auth"
import { api } from "@/lib/api"
import { Hash, Sparkles, X, CheckSquare, BookOpen, Brain, Loader2, Pin } from "lucide-react"
import type { Message } from "@/hooks/use-messages"

interface ExtractedTask {
  title: string
  description?: string
  priority: string
}

function PinnedMessagesButton({ workspaceId, channelId }: { workspaceId: string; channelId: string }) {
  const { data: pins = [] } = usePins(workspaceId, channelId)
  const { mutate: unpinMsg } = useUnpinMessage(channelId)
  const [open, setOpen] = useState(false)

  if (pins.length === 0) return null

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground"
      >
        <Pin size={12} />
        {pins.length} pinned
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 z-20 w-80 bg-popover border rounded-xl shadow-lg overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b">
            <span className="text-xs font-medium">Pinned messages</span>
            <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground"><X size={12} /></button>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {pins.map((pin) => (
              <div key={pin.id} className="flex items-start gap-2 px-3 py-2.5 border-b last:border-0 hover:bg-muted/30 group">
                <Pin size={12} className="text-accent mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs leading-relaxed line-clamp-2">{pin.content}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Pinned by {pin.pinned_by_name}</p>
                </div>
                <button
                  onClick={() => unpinMsg(pin.message_id)}
                  className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all shrink-0"
                  title="Unpin"
                ><X size={12} /></button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

interface MemberInfo {
  id: string
  name: string
}

export default function ChannelPage({
  params,
}: {
  params: Promise<{ workspaceId: string; channelId: string }>
}) {
  const { workspaceId, channelId } = use(params)
  const currentUser = useAuthStore((s) => s.user)
  const currentUserId = currentUser?.id ?? ""

  const { data: messages = [], isLoading } = useMessages(workspaceId, channelId)
  const { mutate: sendMessage } = useSendMessage(workspaceId, channelId)
  const { send } = useWorkspaceSocket(workspaceId, channelId)
  const [threadMsg, setThreadMsg] = useState<Message | null>(null)
  const [taskSource, setTaskSource] = useState<{ id: string; content: string } | null>(null)
  const [suggestedTasks, setSuggestedTasks] = useState<ExtractedTask[]>([])
  const [aiReply, setAiReply] = useState<{ question: string; answer: string } | null>(null)
  const [channelSummary, setChannelSummary] = useState<string | null>(null)

  const { mutate: createTask } = useCreateTask(workspaceId)
  const { extract: extractTasks } = useExtractTasks(workspaceId)
  const { mutateAsync: askKnowledge, isPending: knowledgePending } = useRunKnowledgeAgent(workspaceId)
  const { mutateAsync: runDocs, isPending: docsPending } = useRunDocsAgent(workspaceId)

  const { data: members = [] } = useQuery({
    queryKey: ["members", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/members`).then((r) => r.data as MemberInfo[]),
    staleTime: 60_000,
  })

  const { data: pins = [] } = usePins(workspaceId, channelId)
  const pinnedMessageIds = new Set(pins.map((p) => p.message_id))

  const memberMap = Object.fromEntries(members.map((m) => [m.id, m.name]))

  async function handleSend(content: string) {
    if (content.toLowerCase().startsWith("@ai ")) {
      const question = content.slice(4).trim()
      sendMessage({ content })
      send({ type: "message.new", data: { channel_id: channelId } })
      try {
        const res = await askKnowledge({ question, channel_id: channelId })
        setAiReply({ question, answer: res.answer })
      } catch {
        setAiReply({ question, answer: "AI is unavailable. Check your API key." })
      }
      try {
        const result = await extractTasks(content)
        if (result.tasks.length > 0) setSuggestedTasks(result.tasks)
      } catch { /* ignore */ }
      return
    }
    sendMessage({ content })
    send({ type: "message.new", data: { channel_id: channelId } })
    try {
      const result = await extractTasks(content)
      if (result.tasks.length > 0) setSuggestedTasks(result.tasks)
    } catch { /* ignore */ }
  }

  async function handleSummarize() {
    try {
      const res = await runDocs({ action: "summarize", channel_id: channelId })
      setChannelSummary(res.content)
    } catch {
      setChannelSummary("Summarization failed. Check your API key.")
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main channel area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Channel header */}
        <div className="h-14 border-b flex items-center gap-2 px-4 shrink-0">
          <Hash size={16} className="text-muted-foreground" />
          <span className="font-medium text-sm">Channel</span>
          <span className="text-xs text-muted-foreground">
            {members.length > 0 && `· ${members.length} members`}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <PinnedMessagesButton workspaceId={workspaceId} channelId={channelId} />
            <button
              onClick={handleSummarize}
              disabled={docsPending}
              className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground disabled:opacity-50"
            >
              {docsPending ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
              Summarize
            </button>
          </div>
        </div>

        {/* AI surface: channel summary */}
        {channelSummary && (
          <div className="mx-4 mt-3 p-3 rounded-xl border bg-purple-500/5 border-purple-500/20">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-purple-600 dark:text-purple-400 flex items-center gap-1.5">
                <BookOpen size={12} /> Channel summary
              </span>
              <button onClick={() => setChannelSummary(null)} className="text-muted-foreground hover:text-foreground">
                <X size={12} />
              </button>
            </div>
            <div className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
              {channelSummary}
            </div>
          </div>
        )}

        {/* AI surface: @ai reply */}
        {aiReply && (
          <div className="mx-4 mt-2 p-3 rounded-xl border bg-rose-500/5 border-rose-500/20">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-rose-600 dark:text-rose-400 flex items-center gap-1.5">
                <Brain size={12} /> Knowledge Agent · &quot;{aiReply.question}&quot;
              </span>
              <button onClick={() => setAiReply(null)} className="text-muted-foreground hover:text-foreground">
                <X size={12} />
              </button>
            </div>
            <div className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap">
              {aiReply.answer}
            </div>
          </div>
        )}

        {/* AI surface: task suggestions */}
        {suggestedTasks.length > 0 && (
          <div className="mx-4 mt-3 p-3 rounded-xl border bg-accent/5 border-accent/20">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5 text-xs font-medium text-accent">
                <Sparkles size={12} />
                AI detected {suggestedTasks.length} task{suggestedTasks.length > 1 ? "s" : ""}
              </div>
              <button onClick={() => setSuggestedTasks([])} className="text-muted-foreground hover:text-foreground">
                <X size={12} />
              </button>
            </div>
            <div className="space-y-1.5">
              {suggestedTasks.map((t, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="flex-1 text-xs truncate">{t.title}</span>
                  <button
                    onClick={() => {
                      createTask({ title: t.title, description: t.description, priority: t.priority, status: "todo" })
                      setSuggestedTasks((prev) => prev.filter((_, j) => j !== i))
                    }}
                    className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-md bg-accent/10 text-accent hover:bg-accent/20 transition-colors shrink-0"
                  >
                    <CheckSquare size={11} />
                    Add
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <MessageFeed
          messages={messages}
          isLoading={isLoading}
          members={memberMap}
          currentUserId={currentUserId}
          channelId={channelId}
          pinnedMessageIds={pinnedMessageIds}
          onThreadClick={setThreadMsg}
          onCreateTask={(msg) => setTaskSource({ id: msg.id, content: msg.content })}
        />
        <MessageComposer
          onSend={handleSend}
          workspaceId={workspaceId}
          members={members}
        />
      </div>

      {/* Thread panel */}
      {threadMsg && (
        <ThreadPanel
          parentMessage={threadMsg}
          workspaceId={workspaceId}
          channelId={channelId}
          members={memberMap}
          memberList={members}
          currentUserId={currentUserId}
          onClose={() => setThreadMsg(null)}
        />
      )}

      <CreateTaskDialog
        open={!!taskSource}
        onOpenChange={(open) => { if (!open) setTaskSource(null) }}
        onSubmit={(data) => createTask({ ...data, source_message_id: taskSource?.id })}
        workspaceId={workspaceId}
        sourceMessageContent={taskSource?.content}
      />
    </div>
  )
}
