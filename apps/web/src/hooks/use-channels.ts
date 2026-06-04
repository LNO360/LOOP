import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export function useCreateChannel(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; type: "public" | "private" }) =>
      api.post(`/workspaces/${workspaceId}/channels`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["channels", workspaceId] }),
  })
}
