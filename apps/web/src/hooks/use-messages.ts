import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface Reaction {
  emoji: string
  count: number
  user_ids: string[]
}

export interface Message {
  id: string
  content: string
  author_id: string
  created_at: string
  edited_at: string | null
  thread_id: string | null
  reactions: Reaction[]
}

export function useMessages(workspaceId: string, channelId: string) {
  return useQuery({
    queryKey: ["messages", channelId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/channels/${channelId}/messages`)
        .then((r) => r.data as Message[]),
    refetchInterval: 3000,  // poll every 3s for new messages
  })
}

export function useSendMessage(workspaceId: string, channelId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { content: string; thread_id?: string }) =>
      api
        .post(`/workspaces/${workspaceId}/channels/${channelId}/messages`, data)
        .then((r) => r.data as Message),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", channelId] }),
  })
}

export function useEditMessage(channelId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ messageId, content }: { messageId: string; content: string }) =>
      api.patch(`/messages/${messageId}`, { content }).then((r) => r.data as Message),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", channelId] }),
  })
}

export function useDeleteMessage(channelId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (messageId: string) =>
      api.delete(`/messages/${messageId}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", channelId] }),
  })
}

export function useAddReaction(channelId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ messageId, emoji }: { messageId: string; emoji: string }) =>
      api.post(`/messages/${messageId}/reactions`, { emoji }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", channelId] }),
  })
}

export function useRemoveReaction(channelId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ messageId, emoji }: { messageId: string; emoji: string }) =>
      api.delete(`/messages/${messageId}/reactions/${encodeURIComponent(emoji)}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", channelId] }),
  })
}

export function usePins(workspaceId: string, channelId: string) {
  return useQuery({
    queryKey: ["pins", channelId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/channels/${channelId}/pins`).then(
        (r) => r.data as Array<{ id: string; message_id: string; content: string; pinned_by_name: string; pinned_at: string }>
      ),
    staleTime: 30_000,
  })
}

export function usePinMessage(channelId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (messageId: string) => api.post(`/messages/${messageId}/pin`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pins", channelId] }),
  })
}

export function useUnpinMessage(channelId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (messageId: string) => api.delete(`/messages/${messageId}/pin`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pins", channelId] }),
  })
}
