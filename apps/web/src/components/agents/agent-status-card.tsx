import { AgentStatus } from "@/hooks/use-agent-activity"
import { cn } from "@/lib/utils"
import { Bot, CheckCircle2, Clock, AlertCircle, Zap } from "lucide-react"

interface AgentStatusCardProps {
  agent: AgentStatus
  isActive: boolean // true if agent fired a tool event in the last 30s
}

function statusColor(status: string) {
  if (status === "completed") return "text-green-500"
  if (status === "running") return "text-blue-500 animate-pulse"
  if (status === "error") return "text-red-500"
  return "text-muted-foreground"
}

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") return <CheckCircle2 size={14} className="text-green-500" />
  if (status === "running") return <Zap size={14} className="text-blue-500 animate-pulse" />
  if (status === "error") return <AlertCircle size={14} className="text-red-500" />
  return <Clock size={14} className="text-muted-foreground" />
}

function timeAgo(isoString: string | null): string {
  if (!isoString) return "Never run"
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "Just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function AgentStatusCard({ agent, isActive }: AgentStatusCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border p-4 space-y-3 transition-all",
        isActive && "border-blue-500/50 bg-blue-500/5",
        !isActive && "border-border bg-card"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "p-1.5 rounded-lg",
              isActive ? "bg-blue-500/10" : "bg-muted"
            )}
          >
            <Bot
              size={16}
              className={isActive ? "text-blue-500" : "text-muted-foreground"}
            />
          </div>
          <div>
            <p className="text-sm font-medium leading-none">{agent.display}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{agent.schedule}</p>
          </div>
        </div>
        <StatusIcon status={isActive ? "running" : agent.last_run_status} />
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Last run</span>
          <span className={cn("font-medium", statusColor(agent.last_run_status))}>
            {timeAgo(agent.last_run_at)}
          </span>
        </div>
        {agent.tool_calls_count > 0 && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Tool calls</span>
            <span className="font-medium">{agent.tool_calls_count}</span>
          </div>
        )}
      </div>

      {agent.last_run_summary && (
        <p className="text-xs text-muted-foreground line-clamp-2 border-t pt-2">
          {agent.last_run_summary}
        </p>
      )}

      {isActive && (
        <div className="flex items-center gap-1.5 text-xs text-blue-500">
          <Zap size={12} className="animate-pulse" />
          <span>Running now</span>
        </div>
      )}
    </div>
  )
}
