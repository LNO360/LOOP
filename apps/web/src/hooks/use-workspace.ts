import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export function useWorkspace(workspaceId: string) {
  return useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}`).then((r) => r.data as { id: string; name: string; slug: string }),
    staleTime: 60_000,
  })
}

export function useUpdateWorkspace(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      api.patch(`/workspaces/${workspaceId}`, { name }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspace", workspaceId] }),
  })
}

export function useWorkspaceMembers(workspaceId: string) {
  return useQuery({
    queryKey: ["members", workspaceId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/members`).then(
        (r) =>
          r.data as Array<{
            id: string
            name: string
            email: string
            avatar_url: string | null
            role: string
          }>
      ),
    staleTime: 30_000,
  })
}

export function useRemoveMember(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) =>
      api.delete(`/workspaces/${workspaceId}/members/${userId}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["members", workspaceId] }),
  })
}
