import { AgentActivityEvent } from "@/hooks/use-agent-activity"
import { cn } from "@/lib/utils"
import {
  Database,
  MessageSquare,
  CheckSquare,
  FolderOpen,
  Globe,
  Bell,
  Zap,
} from "lucide-react"

function toolIcon(toolName: string) {
  if (toolName.includes("task")) return <CheckSquare size={12} />
  if (toolName.includes("channel") || toolName.includes("message"))
    return <MessageSquare size={12} />
  if (toolName.includes("project")) return <FolderOpen size={12} />
  if (toolName.includes("workspace") || toolName.includes("list_workspaces"))
    return <Globe size={12} />
  if (toolName.includes("notification")) return <Bell size={12} />
  if (toolName.includes("memory")) return <Database size={12} />
  return <Zap size={12} />
}

function toolLabel(toolName: string): string {
  return toolName.replace("lno_", "").replace(/_/g, " ")
}

function statusDot(status: string) {
  if (status === "done") return "bg-green-500"
  if (status === "running") return "bg-blue-500 animate-pulse"
  if (status === "error") return "bg-red-500"
  return "bg-muted-foreground"
}

function formatTime(isoString: string): string {
  return new Date(isoString).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

interface AgentActivityFeedProps {
  events: AgentActivityEvent[]
  maxVisible?: number
}

export function AgentActivityFeed({
  events,
  maxVisible = 50,
}: AgentActivityFeedProps) {
  const visible = events.slice(0, maxVisible)

  if (visible.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
        <Zap size={24} className="mb-2 opacity-40" />
        <p className="text-sm">No activity yet</p>
        <p className="text-xs mt-1">
          Agent tool calls will appear here in real time
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {visible.map((event, i) => (
        <div
          key={`${event.timestamp}-${i}`}
          className={cn(
            "flex items-start gap-2.5 px-3 py-2 rounded-lg text-xs transition-all",
            i === 0 && "bg-accent/5 border border-accent/20",
            i > 0 && "hover:bg-muted/50"
          )}
        >
          <div className="mt-0.5 text-muted-foreground">
            {toolIcon(event.tool)}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono font-medium text-foreground">
                {toolLabel(event.tool)}
              </span>
              <div
                className={cn(
                  "w-1.5 h-1.5 rounded-full shrink-0",
                  statusDot(event.status)
                )}
              />
            </div>
            {event.summary && (
              <p className="text-muted-foreground truncate mt-0.5">
                {event.summary}
              </p>
            )}
          </div>
          <span className="text-muted-foreground shrink-0 tabular-nums">
            {formatTime(event.timestamp)}
          </span>
        </div>
      ))}
    </div>
  )
}
