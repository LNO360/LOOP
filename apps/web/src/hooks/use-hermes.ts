/**
 * Hooks for Hermes direct chat and user-agent management.
 */
import { useCallback, useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

// ── Types ──────────────────────────────────────────────────────────────────

export interface BuiltinAgent {
  id: string
  name: string
  slug: string
  avatar_emoji: string
  description: string
  schedule: string | null
  builtin: true
  skill: string
}

export interface CustomAgent {
  id: string
  name: string
  slug: string
  avatar_emoji: string
  description: string | null
  schedule: string | null
  model: string | null
  extra_skills: string | null
  active: boolean
  last_run_at: string | null
  run_count: number
  builtin: false
  soul_md?: string
  created_at: string
}

export type Agent = BuiltinAgent | CustomAgent

export interface AgentList {
  builtin: BuiltinAgent[]
  custom: CustomAgent[]
}

export interface ToolCall {
  name: string
  duration?: string
}

export interface ChatMessage {
  id: string
  role: "user" | "hermes"
  content: string
  timestamp: string
  agentSlug?: string
  toolCalls?: ToolCall[]   // MCP / tool calls before the text response
}

// ── Hooks ──────────────────────────────────────────────────────────────────

/** List all agents (built-in + custom) for a workspace. */
export function useHermesAgents(workspaceId: string) {
  return useQuery<AgentList>({
    queryKey: ["hermes-agents", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/hermes/agents`).then(r => r.data),
    enabled: !!workspaceId,
    staleTime: 30_000,
  })
}

/** Get a single custom agent (with soul_md). */
export function useHermesAgent(workspaceId: string, agentId: string | null) {
  return useQuery<{ agent: CustomAgent }>({
    queryKey: ["hermes-agent", workspaceId, agentId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/hermes/agents/${agentId}`).then(r => r.data),
    enabled: !!workspaceId && !!agentId,
  })
}

/** Create a new custom agent. */
export function useCreateAgent(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      name: string
      avatar_emoji?: string
      description?: string
      soul_md: string
      schedule?: string
      model?: string
    }) => api.post(`/workspaces/${workspaceId}/hermes/agents`, body).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hermes-agents", workspaceId] }),
  })
}

/** Update a custom agent. */
export function useUpdateAgent(workspaceId: string, agentId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<CustomAgent> & { soul_md?: string }) =>
      api.put(`/workspaces/${workspaceId}/hermes/agents/${agentId}`, body).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hermes-agents", workspaceId] })
      qc.invalidateQueries({ queryKey: ["hermes-agent", workspaceId, agentId] })
    },
  })
}

/** Delete a custom agent. */
export function useDeleteAgent(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (agentId: string) =>
      api.delete(`/workspaces/${workspaceId}/hermes/agents/${agentId}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hermes-agents", workspaceId] }),
  })
}

/** Trigger an immediate agent run. */
export function useRunAgent(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (agentId: string) =>
      api.post(`/workspaces/${workspaceId}/hermes/agents/${agentId}/run`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hermes-agents", workspaceId] }),
  })
}

/**
 * Stream chat with Hermes via SSE.
 * Returns: messages, sendMessage, isStreaming, error
 */
export function useHermesChat(workspaceId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (content: string, agentSlug?: string) => {
      if (isStreaming) return

      // Add user message immediately
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content,
        timestamp: new Date().toISOString(),
        agentSlug,
      }
      setMessages(prev => [...prev, userMsg])

      // Prepare Hermes response placeholder
      const hermesId = crypto.randomUUID()
      const hermesMsg: ChatMessage = {
        id: hermesId,
        role: "hermes",
        content: "",
        timestamp: new Date().toISOString(),
        agentSlug,
      }
      setMessages(prev => [...prev, hermesMsg])
      setIsStreaming(true)
      setError(null)

      abortRef.current = new AbortController()

      try {
        const token = typeof window !== "undefined"
          ? localStorage.getItem("lno_token") ?? ""
          : ""

        const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
        const resp = await fetch(
          `${apiBase}/api/v1/workspaces/${workspaceId}/hermes/chat`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              message: content,
              agent_slug: agentSlug ?? null,
              max_turns: 12,
            }),
            signal: abortRef.current.signal,
          }
        )

        if (!resp.ok || !resp.body) {
          throw new Error(`HTTP ${resp.status}`)
        }

        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let accumulated = ""
        let toolCalls: ToolCall[] = []

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          // Parse SSE events
          const events = chunk.split("\n\n").filter(Boolean)
          for (const event of events) {
            const line = event.replace(/^data: /, "").trim()
            if (!line) continue
            try {
              const parsed = JSON.parse(line)

              if (parsed.type === "tool") {
                // Tool call event — add to toolCalls array
                toolCalls = [...toolCalls, { name: parsed.name, duration: parsed.duration }]
                setMessages(prev =>
                  prev.map(m =>
                    m.id === hermesId ? { ...m, toolCalls } : m
                  )
                )
              } else if (parsed.error) {
                accumulated = `⚠️ ${parsed.error}`
                setMessages(prev =>
                  prev.map(m =>
                    m.id === hermesId ? { ...m, content: accumulated } : m
                  )
                )
              } else if (parsed.type === "text" || parsed.text) {
                // Text chunk (typed or legacy)
                accumulated += parsed.text ?? ""
                setMessages(prev =>
                  prev.map(m =>
                    m.id === hermesId ? { ...m, content: accumulated } : m
                  )
                )
              }

              if (parsed.done) break
            } catch {
              // Ignore parse errors in SSE stream
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError((err as Error).message)
          setMessages(prev =>
            prev.map(m =>
              m.id === hermesId
                ? { ...m, content: `⚠️ Error: ${(err as Error).message}` }
                : m
            )
          )
        }
      } finally {
        setIsStreaming(false)
        abortRef.current = null
      }
    },
    [workspaceId, isStreaming]
  )

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
    // Fire-and-forget: clear the server-side rolling session summary
    const token = typeof window !== "undefined" ? localStorage.getItem("lno_token") ?? "" : ""
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    fetch(`${apiBase}/api/v1/workspaces/${workspaceId}/hermes/session`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {/* ignore — UI clear never blocks on this */})
  }, [workspaceId])

  return { messages, sendMessage, stopStreaming, clearMessages, isStreaming, error }
}

// ── Hermes config file hooks ───────────────────────────────────────────────

export interface HermesFileResult {
  content: string
  isLoading: boolean
  isSaving: boolean
  saveError: string | null
  save: (content: string) => Promise<void>
  refetch: () => void
}

/**
 * Generic hook for reading and writing a Hermes host file.
 * endpoint: e.g. "soul", "memory", "user-profile", "config"
 */
function useHermesFile(workspaceId: string, endpoint: string): HermesFileResult {
  const qc = useQueryClient()
  const queryKey = ["hermes-file", workspaceId, endpoint]

  const { data, isLoading, refetch } = useQuery<{ content: string }>({
    queryKey,
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/hermes/${endpoint}`).then(r => r.data),
    enabled: !!workspaceId,
    staleTime: 10_000,
  })

  const mutation = useMutation({
    mutationFn: (content: string) =>
      api.put(`/workspaces/${workspaceId}/hermes/${endpoint}`, { content }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })

  return {
    content: data?.content ?? "",
    isLoading,
    isSaving: mutation.isPending,
    saveError: mutation.error ? (mutation.error as Error).message : null,
    save: (content: string) => mutation.mutateAsync(content),
    refetch,
  }
}

export const useSoulMd        = (workspaceId: string) => useHermesFile(workspaceId, "soul")
export const useMemoryMd      = (workspaceId: string) => useHermesFile(workspaceId, "memory")
export const useUserProfile   = (workspaceId: string) => useHermesFile(workspaceId, "user-profile")
export const useHermesConfig  = (workspaceId: string) => useHermesFile(workspaceId, "config")

/**
 * One-shot streaming call to Hermes.
 * Calls the chat endpoint and streams output via onChunk callback.
 * Returns an AbortController to cancel the stream.
 */
export function streamHermes(
  workspaceId: string,
  prompt: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): AbortController {
  const abort = new AbortController()
  const token = typeof window !== "undefined"
    ? localStorage.getItem("lno_token") ?? ""
    : ""
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

  ;(async () => {
    try {
      const resp = await fetch(
        `${apiBase}/api/v1/workspaces/${workspaceId}/hermes/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ message: prompt, max_turns: 5 }),
          signal: abort.signal,
        }
      )
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        for (const event of chunk.split("\n\n").filter(Boolean)) {
          const line = event.replace(/^data: /, "").trim()
          if (!line) continue
          try {
            const parsed = JSON.parse(line)
            // Handle typed events (new) and legacy text events
            if (parsed.type === "text" || (parsed.text && parsed.type !== "tool" && parsed.type !== "done")) {
              if (parsed.text) onChunk(parsed.text)
            }
            if (parsed.done) { onDone(); return }
          } catch { /* skip malformed SSE */ }
        }
      }
      onDone()
    } catch (err) {
      if ((err as Error).name !== "AbortError") onError((err as Error).message)
    }
  })()

  return abort
}

// ── AgentTeam types ───────────────────────────────────────────────────────

export interface AgentTeamMember {
  agent_id: string
  agent_name: string
  agent_slug: string
  avatar_emoji: string
  team_role: "coordinator" | "specialist"
}

export interface AgentTeam {
  id: string
  name: string
  description: string | null
  goal: string | null
  created_at: string
  members: AgentTeamMember[]
}

export interface TeamList {
  teams: AgentTeam[]
}

// ── AgentTeam hooks ───────────────────────────────────────────────────────

/** List all agent teams for a workspace. */
export function useAgentTeams(workspaceId: string) {
  return useQuery<TeamList>({
    queryKey: ["hermes-teams", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/hermes/teams`).then(r => r.data),
    enabled: !!workspaceId,
    staleTime: 30_000,
  })
}

/** Create a new agent team. */
export function useCreateTeam(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; description?: string; goal?: string }) =>
      api.post(`/workspaces/${workspaceId}/hermes/teams`, body).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hermes-teams", workspaceId] }),
  })
}

/** Update an existing agent team. */
export function useUpdateTeam(workspaceId: string, teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name?: string; description?: string; goal?: string }) =>
      api.put(`/workspaces/${workspaceId}/hermes/teams/${teamId}`, body).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hermes-teams", workspaceId] }),
  })
}

/** Delete an agent team. */
export function useDeleteTeam(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (teamId: string) =>
      api.delete(`/workspaces/${workspaceId}/hermes/teams/${teamId}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hermes-teams", workspaceId] }),
  })
}

/** Add a member to an agent team. */
export function useAddTeamMember(workspaceId: string, teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { agent_id: string; team_role: "coordinator" | "specialist" }) =>
      api.post(`/workspaces/${workspaceId}/hermes/teams/${teamId}/members`, body).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hermes-teams", workspaceId] }),
  })
}

/** Remove a member from an agent team. */
export function useRemoveTeamMember(workspaceId: string, teamId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (agentId: string) =>
      api.delete(`/workspaces/${workspaceId}/hermes/teams/${teamId}/members/${agentId}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hermes-teams", workspaceId] }),
  })
}
