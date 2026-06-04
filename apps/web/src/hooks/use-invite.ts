// apps/web/src/hooks/use-invite.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface InviteInfo {
  workspace_id: string
  workspace_name: string
  workspace_emoji: string
  inviter_name: string
}

export interface InviteLink {
  token: string
  url: string
}

/** Fetch invite metadata (public — no auth needed). */
export function useInviteInfo(token: string | null) {
  return useQuery<InviteInfo>({
    queryKey: ["invite", token],
    queryFn: () => api.get(`/invites/${token}`).then((r) => r.data),
    enabled: !!token,
    retry: false,
    staleTime: 60_000,
  })
}

/** Generate (or return existing) invite link for a workspace. */
export function useCreateInviteLink(workspaceId: string) {
  return useMutation<InviteLink>({
    mutationFn: () =>
      api.post(`/workspaces/${workspaceId}/invite-link`).then((r) => r.data),
  })
}

/** Accept an invite — must be authenticated. Returns { workspace_id }. */
export function useAcceptInvite() {
  const qc = useQueryClient()
  return useMutation<{ workspace_id: string }, unknown, string>({
    mutationFn: (token: string) =>
      api.post(`/invites/${token}/accept`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integrations"] })
    },
  })
}
