import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"

// ── Types ─────────────────────────────────────────────────────────────────────

export type DebateMode = "round_robin" | "structured" | "dynamic"

export interface BoardroomTool {
  name: string
  category: "research" | "workspace_read" | "workspace_write" | "calc"
  label: string
  description: string
  risk: "low" | "medium"
}

export interface ToolEvent {
  tool: string
  args?: Record<string, unknown>
  summary: string
}

export interface BoardroomAgentDef {
  name: string
  emoji: string
  persona_type: "builtin" | "custom" | "adhoc"
  agent_ref?: string
  system_prompt: string
  turn_order: number
  tools?: string[] | null // null/undefined = inherit session default_tools
}

export interface BoardroomAgent extends BoardroomAgentDef {
  id: string
  session_id: string
}

export interface BoardroomTurn {
  role: "agent" | "moderator"
  agent_id?: string
  name: string
  emoji?: string
  content: string
  round?: number
  tool_events?: ToolEvent[]
}

export interface BoardroomOutput {
  plan: string
  proposed_tasks: Array<{
    title: string
    description: string | null
    priority: "low" | "medium" | "high" | "urgent"
  }>
}

export interface BoardroomSession {
  id: string
  workspace_id: string
  topic: string
  status: "setup" | "running" | "paused" | "synthesizing" | "done"
  rounds_config: number
  debate_mode: DebateMode
  default_tools: string[]
  transcript: BoardroomTurn[]
  output: BoardroomOutput | null
  agents: BoardroomAgent[]
  created_at: string
  updated_at: string
}

export interface SseEvent {
  type:
    | "turn_start"
    | "turn_end"
    | "tool_call"
    | "tool_result"
    | "phase_start"
    | "moderator_challenge"
    | "interject_ack"
    | "stopping"
    | "synthesis_start"
    | "synthesis_delta"
    | "plan_ready"
    | "session_done"
  agent?: { id: string; name: string; emoji: string }
  agent_id?: string
  full_text?: string
  content?: string
  text?: string
  plan?: string
  proposed_tasks?: BoardroomOutput["proposed_tasks"]
  round?: number
  total_rounds?: number
  // tool_call / tool_result
  tool?: string
  args?: Record<string, unknown>
  summary?: string
  tool_events?: ToolEvent[]
  // phase_start
  phase?: string
}

// ── Query hooks ───────────────────────────────────────────────────────────────

export function useBoardroomSessions(workspaceId: string) {
  return useQuery({
    queryKey: ["boardroom-sessions", workspaceId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/boardroom/sessions`)
        .then((r) => r.data.sessions as BoardroomSession[]),
  })
}

export function useBoardroomTools(workspaceId: string) {
  return useQuery({
    queryKey: ["boardroom-tools", workspaceId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/boardroom/tools`)
        .then((r) => r.data.tools as BoardroomTool[]),
    staleTime: 1000 * 60 * 60, // catalog is static
  })
}

export function useBoardroomSession(workspaceId: string, sessionId: string | null) {
  return useQuery({
    queryKey: ["boardroom-session", workspaceId, sessionId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/boardroom/sessions/${sessionId}`)
        .then((r) => r.data as BoardroomSession),
    enabled: !!sessionId,
  })
}

// ── Mutation hooks ────────────────────────────────────────────────────────────

export function useCreateBoardroomSession(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      topic: string
      rounds_config: number
      debate_mode: DebateMode
      default_tools: string[]
      agents: BoardroomAgentDef[]
    }) =>
      api
        .post(`/workspaces/${workspaceId}/boardroom/sessions`, body)
        .then((r) => r.data as BoardroomSession),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boardroom-sessions", workspaceId] }),
  })
}

export function useInterject(workspaceId: string, sessionId: string) {
  return useMutation({
    mutationFn: (message: string) =>
      api
        .post(`/workspaces/${workspaceId}/boardroom/sessions/${sessionId}/interject`, {
          message,
        })
        .then((r) => r.data),
  })
}

export function useStopSession(workspaceId: string, sessionId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api
        .post(`/workspaces/${workspaceId}/boardroom/sessions/${sessionId}/stop`)
        .then((r) => r.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["boardroom-session", workspaceId, sessionId] }),
  })
}

export function useApplyTasks(workspaceId: string, sessionId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (taskIds: number[] | null) =>
      api
        .post(`/workspaces/${workspaceId}/boardroom/sessions/${sessionId}/apply`, {
          task_ids: taskIds,
        })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks", workspaceId] }),
  })
}

// ── SSE hook ──────────────────────────────────────────────────────────────────

export interface UseBoardroomStreamOptions {
  workspaceId: string
  sessionId: string
  onEvent: (event: SseEvent) => void
  onDone: () => void
}

export function useBoardroomStream({
  workspaceId,
  sessionId,
  onEvent,
  onDone,
}: UseBoardroomStreamOptions) {
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

  const start = useCallback(async (overrideSessionId?: string) => {
    const sid = overrideSessionId ?? sessionId
    if (!sid) {
      setError("No session id")
      return
    }
    const token = typeof window !== "undefined" ? localStorage.getItem("lno_token") : null
    setStreaming(true)
    setError(null)
    abortRef.current = new AbortController()

    try {
      const res = await fetch(
        `${baseUrl}/api/v1/workspaces/${workspaceId}/boardroom/sessions/${sid}/start`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "text/event-stream",
          },
          signal: abortRef.current.signal,
        }
      )
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event: SseEvent = JSON.parse(line.slice(6))
              onEvent(event)
              if (event.type === "session_done") {
                setStreaming(false)
                onDone()
                return
              }
            } catch {
              // malformed line; skip
            }
          }
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== "AbortError") {
        setError(e.message)
      }
    } finally {
      setStreaming(false)
    }
  }, [workspaceId, sessionId, baseUrl, onEvent, onDone])

  const stop = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { start, stop, streaming, error }
}
