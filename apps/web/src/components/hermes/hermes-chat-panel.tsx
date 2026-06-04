"use client"
import { useRef, useEffect, useState, KeyboardEvent } from "react"
import { useHermesChat, type Agent } from "@/hooks/use-hermes"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  Bot,
  Send,
  Square,
  Trash2,
  ChevronDown,
  Loader2,
  Zap,
} from "lucide-react"

interface HermesChatPanelProps {
  workspaceId: string
  /** If provided, routes chat to this specific agent */
  agent?: Agent | null
  className?: string
  /** Override default suggestion chips */
  suggestions?: string[]
  /** Override header description */
  subtitle?: string
  /** Auto-send on mount (once) */
  initialMessage?: string
}

const DEFAULT_SUGGESTIONS = [
  "What's the status of all projects?",
  "Find any overdue tasks and notify the assignees",
  "Give me a team activity summary",
]

export function HermesChatPanel({
  workspaceId,
  agent,
  className,
  suggestions,
  subtitle,
  initialMessage,
}: HermesChatPanelProps) {
  const { messages, sendMessage, stopStreaming, clearMessages, isStreaming, error } =
    useHermesChat(workspaceId)
  const [input, setInput] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const initialSentRef = useRef(false)

  // Auto-scroll to bottom as Hermes streams
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    if (initialMessage && !initialSentRef.current && !isStreaming) {
      initialSentRef.current = true
      sendMessage(initialMessage, agent?.slug ?? undefined)
    }
  }, [initialMessage, sendMessage, isStreaming, agent?.slug])

  const handleSend = () => {
    const msg = input.trim()
    if (!msg || isStreaming) return
    setInput("")
    sendMessage(msg, agent?.slug ?? undefined)
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = "auto"
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const agentName = agent?.name ?? "Hermes"
  const agentEmoji = agent?.avatar_emoji ?? "🤖"
  const chips = suggestions ?? DEFAULT_SUGGESTIONS
  const description = subtitle ?? agent?.description ?? "Full access to all workspace tools"

  return (
    <div className={cn("flex flex-col h-full bg-background", className)}>
      {/* Header */}
      <div className="border-b px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xl">{agentEmoji}</span>
          <div>
            <p className="text-sm font-semibold leading-none">{agentName}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {isStreaming && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 size={12} className="animate-spin" />
              thinking…
            </span>
          )}
          {messages.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clearMessages} className="h-7 text-xs">
              <Trash2 size={12} className="mr-1" />
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground py-16">
            <span className="text-5xl mb-4">{agentEmoji}</span>
            <p className="text-sm font-medium">Chat with {agentName}</p>
            <p className="text-xs mt-1 max-w-xs">
              {description}
            </p>
            <div className="mt-6 grid grid-cols-1 gap-2 w-full max-w-sm">
              {chips.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => sendMessage(suggestion, agent?.slug ?? undefined)}
                  className="text-left text-xs px-3 py-2 rounded-lg border hover:bg-muted transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "flex gap-3 max-w-full",
              msg.role === "user" ? "flex-row-reverse" : "flex-row"
            )}
          >
            {/* Avatar */}
            <div
              className={cn(
                "h-7 w-7 shrink-0 rounded-full flex items-center justify-center text-sm",
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
              )}
            >
              {msg.role === "user" ? "U" : agentEmoji}
            </div>

            {/* Bubble */}
            <div
              className={cn(
                "rounded-2xl px-4 py-2.5 text-sm max-w-[85%] whitespace-pre-wrap break-words",
                msg.role === "user"
                  ? "bg-primary text-primary-foreground rounded-tr-sm"
                  : "bg-muted text-foreground rounded-tl-sm"
              )}
            >
              {msg.content || (
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <Loader2 size={12} className="animate-spin" />
                  typing…
                </span>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t px-4 py-3 shrink-0">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            className="flex-1 resize-none rounded-xl border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring min-h-[40px] max-h-40"
            placeholder={`Message ${agentName}… (Shift+Enter for new line)`}
            rows={1}
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              // Auto-resize
              e.target.style.height = "auto"
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
            }}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          {isStreaming ? (
            <Button
              size="sm"
              variant="destructive"
              className="h-9 w-9 p-0 rounded-xl shrink-0"
              onClick={stopStreaming}
            >
              <Square size={14} />
            </Button>
          ) : (
            <Button
              size="sm"
              className="h-9 w-9 p-0 rounded-xl shrink-0"
              onClick={handleSend}
              disabled={!input.trim()}
            >
              <Send size={14} />
            </Button>
          )}
        </div>
        <p className="text-[10px] text-muted-foreground mt-1.5 text-center">
          <Zap size={10} className="inline mr-0.5" />
          Full MCP access · reads and writes workspace data
        </p>
      </div>
    </div>
  )
}
