import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface AgentInfo {
  type: string
  model: string
  trigger: string
  description: string
}

export interface Memory {
  id: string
  key: string
  content: string
  importance: number   // 1-5
  source: string       // "ai" | "manual"
  updated_at: string | null
}

export function useAgentStatus(workspaceId: string) {
  return useQuery({
    queryKey: ["agents-status", workspaceId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/agents/status`).then((r) => r.data as { agents: AgentInfo[]; ai_enabled: boolean }),
    staleTime: 30_000,
  })
}

export function useRunProjectManager(workspaceId: string) {
  return useMutation({
    mutationFn: (data: { project_id: string; project_name: string }) =>
      api.post(`/workspaces/${workspaceId}/agents/project_manager/run`, data).then((r) => r.data as {
        health: "on_track" | "at_risk" | "blocked"
        summary: string
        blockers: string[]
        suggestions: string[]
      }),
  })
}

export function useRunDocsAgent(workspaceId: string) {
  return useMutation({
    mutationFn: (data: { action: "draft" | "summarize" | "improve"; content?: string; channel_id?: string }) =>
      api.post(`/workspaces/${workspaceId}/agents/docs/run`, data).then((r) => r.data as { content: string }),
  })
}

export function useRunKnowledgeAgent(workspaceId: string) {
  return useMutation({
    mutationFn: (data: { question: string; channel_id?: string }) =>
      api.post(`/workspaces/${workspaceId}/agents/knowledge/run`, data).then((r) => r.data as { answer: string; sources_used: number }),
  })
}

export function useRunDigest(workspaceId: string) {
  return useMutation({
    mutationFn: () =>
      api.post(`/workspaces/${workspaceId}/agents/digest/run`, {}).then((r) => r.data as { content: string }),
  })
}

// ── Memory hooks ─────────────────────────────────────────────

export function useMemories(workspaceId: string) {
  return useQuery({
    queryKey: ["memories", workspaceId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/agents/memory`).then(
        (r) => r.data as { memories: Memory[]; count: number }
      ),
    staleTime: 10_000,
  })
}

export function useAddMemory(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { key: string; content: string; importance?: number }) =>
      api.post(`/workspaces/${workspaceId}/agents/memory`, { importance: 3, ...data }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memories", workspaceId] })
    },
  })
}

export function useDeleteMemory(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (memoryId: string) =>
      api.delete(`/workspaces/${workspaceId}/agents/memory/${memoryId}`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memories", workspaceId] })
    },
  })
}
