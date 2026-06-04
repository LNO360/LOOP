// apps/web/src/hooks/use-integrations.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface IntegrationStatus {
  provider: "google" | "brave" | "github"
  connected: boolean
  expired?: boolean
  account_email?: string
  scopes?: string
  connected_at?: string
  key_set?: boolean
}

export interface GithubAppStatus {
  installed: boolean
  account_login: string | null
  installation_id: string | null
  installed_at: string | null
}

export interface GithubEventItem {
  id: string
  event_type: string
  action: string | null
  repo_full_name: string | null
  status: string
  received_at: string | null
  processed_at: string | null
}

export interface IntegrationsResponse {
  integrations: IntegrationStatus[]
  github_app: GithubAppStatus
  github_app_install_url: string | null
}

/** List all integration statuses for the workspace. */
export function useIntegrations(workspaceId: string) {
  return useQuery<IntegrationsResponse>({
    queryKey: ["integrations", workspaceId],
    queryFn: () =>
      api.get(`/workspaces/${workspaceId}/integrations`).then((r) => r.data),
    enabled: !!workspaceId,
    staleTime: 30_000,
  })
}

/** Get the Google OAuth URL, then redirect the user to it. */
export function useGoogleConnect(workspaceId: string) {
  return useMutation({
    mutationFn: () =>
      api
        .get(`/workspaces/${workspaceId}/integrations/google/connect`)
        .then((r) => r.data as { url: string }),
    onSuccess: ({ url }) => {
      window.location.href = url
    },
    // errors are shown inline in the GoogleCard via mutation.isError / mutation.error
  })
}

/** Disconnect Google from this workspace. */
export function useGoogleDisconnect(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api
        .delete(`/workspaces/${workspaceId}/integrations/google`)
        .then((r) => r.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["integrations", workspaceId] }),
  })
}

/** Get the GitHub OAuth URL, then redirect the user to it. */
export function useGitHubConnect(workspaceId: string) {
  return useMutation({
    mutationFn: () =>
      api
        .get(`/workspaces/${workspaceId}/integrations/github/connect`)
        .then((r) => r.data as { url: string }),
    onSuccess: ({ url }) => {
      window.location.href = url
    },
  })
}

/** Disconnect GitHub from this workspace. */
export function useGitHubDisconnect(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api
        .delete(`/workspaces/${workspaceId}/integrations/github`)
        .then((r) => r.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["integrations", workspaceId] }),
  })
}

/** Save (or update) the Brave Search API key. */
export function useSaveBraveKey(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (api_key: string) =>
      api
        .put(`/workspaces/${workspaceId}/integrations/brave`, { api_key })
        .then((r) => r.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["integrations", workspaceId] }),
  })
}

/** Remove the Brave Search API key. */
export function useRemoveBraveKey(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api
        .delete(`/workspaces/${workspaceId}/integrations/brave`)
        .then((r) => r.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["integrations", workspaceId] }),
  })
}

/** Redirect to GitHub App install page. Uses authenticated connect route for signed state. */
export function useGitHubAppInstall(workspaceId: string) {
  return useMutation({
    mutationFn: async () => {
      const resp = await api.get<{ url: string }>(
        `/workspaces/${workspaceId}/integrations/github-app/connect`
      )
      if (!resp.data.url) throw new Error("GITHUB_APP_NAME not configured on server")
      window.location.href = resp.data.url
    },
  })
}

/** Uninstall the GitHub App for this workspace. */
export function useGitHubAppUninstall(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api
        .delete(`/workspaces/${workspaceId}/integrations/github-app`)
        .then((r) => r.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["integrations", workspaceId] }),
  })
}

/** Fetch recent GitHub webhook events for the UI feed. */
export function useGitHubEvents(workspaceId: string, limit = 20) {
  return useQuery<{ events: GithubEventItem[] }>({
    queryKey: ["github-events", workspaceId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/github/events?limit=${limit}`)
        .then((r) => r.data),
    enabled: !!workspaceId,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
}
