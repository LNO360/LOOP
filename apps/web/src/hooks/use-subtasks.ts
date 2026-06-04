import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export function useSubtasks(workspaceId: string, taskId: string | null) {
  return useQuery({
    queryKey: ["subtasks", taskId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/tasks/${taskId}/subtasks`).then((r) => r.data),
    enabled: !!taskId,
  })
}

export function useCreateSubtask(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { title: string; parent_task_id: string; priority?: string }) =>
      api.post(`/workspaces/${workspaceId}/tasks`, data).then((r) => r.data),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["subtasks", vars.parent_task_id] })
      qc.invalidateQueries({ queryKey: ["tasks", workspaceId] })
    },
  })
}

export function useUpdateSubtask(workspaceId: string, parentTaskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, data }: { taskId: string; data: { status?: string; title?: string } }) =>
      api.patch(`/workspaces/${workspaceId}/tasks/${taskId}`, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subtasks", parentTaskId] })
    },
  })
}
