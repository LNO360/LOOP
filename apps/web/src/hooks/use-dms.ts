import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export function useDMs(workspaceId: string) {
  return useQuery({
    queryKey: ["dms", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/dms`).then((r) => r.data),
  })
}

export function useCreateDM(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) =>
      api.post(`/workspaces/${workspaceId}/dm`, { user_id: userId }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dms", workspaceId] }),
  })
}
