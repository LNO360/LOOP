"use client"
import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

// ── Types ──────────────────────────────────────────────────────

export interface AgentStatus {
  name: string
  display: string
  schedule: string
  last_run_at: string | null
  last_run_status: string
  last_run_summary: string | null
  tool_calls_count: number
}

export interface AgentStatusResponse {
  agents: AgentStatus[]
  pending_actions: number
  weekly_runs: number
}

export interface AgentActivityEvent {
  type: string       // "agent:tool_call"
  tool: string       // "lno_list_tasks"
  status: string     // "running" | "done" | "error"
  summary: string
  timestamp: string  // added client-side
}

// ── REST: agent status (last runs + counts) ───────────────────

export function useAgentStatus(workspaceId: string) {
  return useQuery<AgentStatusResponse>({
    queryKey: ["agent-status", workspaceId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/agent-status`).then((r) => r.data),
    refetchInterval: 30_000,
    enabled: !!workspaceId,
  })
}

// ── WebSocket: live agent activity feed ───────────────────────

export function useAgentActivityFeed(workspaceId: string) {
  const [events, setEvents] = useState<AgentActivityEvent[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!workspaceId) return

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"}/ws/${workspaceId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type?.startsWith("agent:")) {
          setEvents((prev) => [
            { ...data, timestamp: new Date().toISOString() },
            ...prev.slice(0, 99), // keep last 100 events
          ])
        }
      } catch {
        // ignore malformed frames
      }
    }

    return () => {
      ws.close()
    }
  }, [workspaceId])

  function clearEvents() {
    setEvents([])
  }

  return { events, clearEvents }
}
