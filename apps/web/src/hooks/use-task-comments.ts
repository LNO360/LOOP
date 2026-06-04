import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface TaskComment {
  id: string
  content: string
  author_id: string
  author_name: string
  created_at: string
}

export function useTaskComments(workspaceId: string, taskId: string | null) {
  return useQuery({
    queryKey: ["task-comments", taskId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/tasks/${taskId}/comments`)
        .then((r) => r.data as TaskComment[]),
    enabled: !!taskId,
  })
}

export function useAddComment(workspaceId: string, taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (content: string) =>
      api
        .post(`/workspaces/${workspaceId}/tasks/${taskId}/comments`, { content })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task-comments", taskId] }),
  })
}

export function useDeleteComment(workspaceId: string, taskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (commentId: string) =>
      api.delete(
        `/workspaces/${workspaceId}/tasks/${taskId}/comments/${commentId}`
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task-comments", taskId] }),
  })
}
