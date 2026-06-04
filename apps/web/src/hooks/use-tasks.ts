import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface Task {
  id: string
  title: string
  description?: string
  status: string
  priority: string
  assignee_id?: string | null
  assignee_ids?: string[]
  assignee_names?: string[]
  due_date?: string | null
  project_id?: string | null
  parent_task_id?: string | null
  source_message_id?: string | null
  created_at: string
  tags: string[]
}

export function useTasks(
  workspaceId: string,
  filters?: { status?: string; assignee_id?: string; project_id?: string }
) {
  return useQuery<Task[]>({
    queryKey: ["tasks", workspaceId, filters],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/tasks`, { params: filters }).then((r) => r.data),
  })
}

export function useProjectTasks(workspaceId: string, projectId: string) {
  return useQuery<Task[]>({
    queryKey: ["tasks", workspaceId, { project_id: projectId }],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/tasks`, { params: { project_id: projectId } })
        .then((r) => r.data),
    staleTime: 10_000,
  })
}

export function useCreateTask(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.post(`/workspaces/${workspaceId}/tasks`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks", workspaceId] }),
  })
}

export function useUpdateTask(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, data }: { taskId: string; data: Record<string, unknown> }) =>
      api.patch(`/workspaces/${workspaceId}/tasks/${taskId}`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks", workspaceId] }),
  })
}

export function useDeleteTask(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (taskId: string) =>
      api.delete(`/workspaces/${workspaceId}/tasks/${taskId}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks", workspaceId] }),
  })
}
