/**
 * useWorkspaceIntelligence — fetches the fast workspace intelligence analysis.
 *
 * Returns health_score, risk_signals[], suggested_prompts[], stats{}.
 * Cached 5 min; stale-while-revalidate for instant subsequent renders.
 */
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface WorkspaceStats {
  open_tasks: number
  overdue_tasks: number
  urgent_tasks: number
  this_week_tasks: number
  unassigned_high_tasks: number
  total_projects: number
  active_projects: number
  at_risk_projects: number
  pending_actions: number
}

export interface WorkspaceIntelligence {
  health_score: number          // 0–100
  risk_signals: string[]        // plain-English risk bullets e.g. "🔴 5 tasks overdue"
  suggested_prompts: string[]   // 4 context-aware chat prompt strings
  stats: WorkspaceStats
}

export function useWorkspaceIntelligence(workspaceId: string) {
  return useQuery<WorkspaceIntelligence>({
    queryKey: ["workspace-intelligence", workspaceId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/intelligence`)
        .then((r) => r.data),
    enabled: !!workspaceId,
    staleTime: 5 * 60 * 1000,   // 5 minutes
    refetchOnWindowFocus: false,
  })
}
