import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { Message } from "./use-messages"

export function useThread(workspaceId: string, channelId: string, messageId: string | null) {
  return useQuery({
    queryKey: ["thread", messageId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/channels/${channelId}/messages/${messageId}/thread`)
        .then((r) => r.data as Message[]),
    enabled: !!messageId,
    refetchInterval: 3000,
  })
}

export function useReplyToThread(workspaceId: string, channelId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { content: string; thread_id: string }) =>
      api
        .post(`/workspaces/${workspaceId}/channels/${channelId}/messages`, data)
        .then((r) => r.data as Message),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["thread", vars.thread_id] })
      qc.invalidateQueries({ queryKey: ["messages", channelId] })
    },
  })
}
