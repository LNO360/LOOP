"use client"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface ProposedAction {
  id: string
  workspace_id: string
  run_id: string | null
  action_type: string
  payload: Record<string, unknown>
  risk_level: "low" | "medium" | "high"
  status: "pending" | "approved" | "rejected" | "executed" | "failed"
  proposed_at: string
  decided_at: string | null
  decided_by: string | null
  execution_result: Record<string, unknown> | null
}

export interface AgentRun {
  id: string
  trigger_type: string
  agent_name: string
  status: "running" | "success" | "error" | "no_actions"
  started_at: string
  finished_at: string | null
  result_summary: string | null
}

export function useProposedActions(
  workspaceId: string,
  status: string = "pending"
) {
  return useQuery<{ actions: ProposedAction[]; count: number }>({
    queryKey: ["proposed-actions", workspaceId, status],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/proposed-actions`, {
          params: { status },
        })
        .then((r) => r.data),
    refetchInterval: 30_000,
  })
}

export function useApproveAction(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (actionId: string) =>
      api
        .post(`/workspaces/${workspaceId}/proposed-actions/${actionId}/approve`)
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proposed-actions", workspaceId] })
    },
  })
}

export function useRejectAction(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (actionId: string) =>
      api
        .post(`/workspaces/${workspaceId}/proposed-actions/${actionId}/reject`)
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proposed-actions", workspaceId] })
    },
  })
}

export function useAgentRuns(workspaceId: string) {
  return useQuery<{ runs: AgentRun[]; count: number }>({
    queryKey: ["agent-runs", workspaceId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/agent-runs`)
        .then((r) => r.data),
    staleTime: 30_000,
  })
}
