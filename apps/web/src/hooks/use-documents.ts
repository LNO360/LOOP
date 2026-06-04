import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export function useDocuments(workspaceId: string) {
  return useQuery({
    queryKey: ["documents", workspaceId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/documents`).then((r) => r.data),
  })
}

export function useDocument(workspaceId: string, docId: string) {
  return useQuery({
    queryKey: ["document", docId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/documents/${docId}`).then((r) => r.data),
    enabled: !!docId,
  })
}

export function useCreateDocument(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { title: string; content?: unknown }) =>
      api.post(`/workspaces/${workspaceId}/documents`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", workspaceId] }),
  })
}

export function useUpdateDocument(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ docId, data }: { docId: string; data: Record<string, unknown> }) =>
      api.patch(`/workspaces/${workspaceId}/documents/${docId}`, data).then((r) => r.data),
    onSuccess: (_, { docId }) => {
      qc.invalidateQueries({ queryKey: ["document", docId] })
      qc.invalidateQueries({ queryKey: ["documents", workspaceId] })
    },
  })
}
