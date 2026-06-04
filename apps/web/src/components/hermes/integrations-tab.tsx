"use client"
import { useState, useEffect } from "react"
import { useSearchParams } from "next/navigation"
import { useQueryClient } from "@tanstack/react-query"
import {
  useIntegrations,
  useGoogleConnect,
  useGoogleDisconnect,
  useGitHubConnect,
  useGitHubDisconnect,
  useSaveBraveKey,
  useRemoveBraveKey,
  useGitHubAppInstall,
  useGitHubAppUninstall,
  useGitHubEvents,
  type IntegrationStatus,
  type GithubAppStatus,
  type GithubEventItem,
} from "@/hooks/use-integrations"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  CheckCircle, AlertTriangle, XCircle, ExternalLink,
  Eye, EyeOff, Trash2, Globe,
  GitBranch, GitPullRequest, AlertCircle, Package, SkipForward, Loader2,
} from "lucide-react"
import {
  IntegrationBrandIcon,
  GoogleProductIcons,
  GoogleHermesToolsPanel,
  GOOGLE_WORKSPACE_PRODUCTS,
} from "@/components/hermes/integration-logos"

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ integration, overrideConnected }: { integration: IntegrationStatus; overrideConnected?: boolean }) {
  const isConnected = (overrideConnected ?? integration.connected) && !integration.expired
  const isExpired = integration.connected && integration.expired

  if (isConnected) {
    return (
      <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
        <CheckCircle size={11} /> Connected
      </span>
    )
  }
  if (isExpired) {
    return (
      <span className="flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
        <AlertTriangle size={11} /> Token expired
      </span>
    )
  }
  return (
    <span className="flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
      <XCircle size={11} /> Not connected
    </span>
  )
}

// ── Google card ───────────────────────────────────────────────────────────────

function GoogleCard({
  workspaceId,
  integration,
}: {
  workspaceId: string
  integration: IntegrationStatus
}) {
  const connectMutation = useGoogleConnect(workspaceId)
  const disconnectMutation = useGoogleDisconnect(workspaceId)
  const isConnected = integration.connected && !integration.expired

  const connectError =
    connectMutation.isError
      ? ((connectMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
         "Could not start Google sign-in. Make sure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are configured on the server.")
      : null

  return (
    <div className="rounded-2xl border border-border/60 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <IntegrationBrandIcon provider="google" />
          <div>
            <p className="font-medium text-sm">Google Workspace</p>
            <p className="text-xs text-muted-foreground">
              {GOOGLE_WORKSPACE_PRODUCTS.map(p => p.label).join(" · ")}
            </p>
          </div>
        </div>
        <StatusBadge integration={integration} />
      </div>

      <div className="mt-4">
        <GoogleProductIcons />
      </div>

      {isConnected && integration.account_email && (
        <div className="mt-4 rounded-xl bg-muted/40 px-3 py-2.5 text-xs space-y-1">
          <p>
            <span className="text-muted-foreground">Account:</span>{" "}
            <span className="font-medium">{integration.account_email}</span>
          </p>
          {integration.connected_at && (
            <p>
              <span className="text-muted-foreground">Connected:</span>{" "}
              {new Date(integration.connected_at).toLocaleDateString()}
            </p>
          )}
          <p className="text-muted-foreground pt-1">
            Reconnect if you connected before Sheets/Meet/Search Console were added — new OAuth scopes are required.
          </p>
        </div>
      )}

      <div className="mt-4 space-y-2">
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive border-destructive/30 hover:bg-red-50"
              onClick={() => disconnectMutation.mutate()}
              disabled={disconnectMutation.isPending}
            >
              <Trash2 size={13} className="mr-1.5" />
              {disconnectMutation.isPending ? "Disconnecting…" : "Disconnect"}
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => connectMutation.mutate()}
              disabled={connectMutation.isPending}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              <ExternalLink size={13} className="mr-1.5" />
              {connectMutation.isPending
                ? "Redirecting…"
                : integration.expired
                ? "Reconnect"
                : "Connect Google"}
            </Button>
          )}
          {integration.expired && (
            <p className="text-xs text-amber-600">Token expired — reconnect to restore access.</p>
          )}
        </div>
        {connectError && (
          <p className="flex items-center gap-1.5 text-xs text-red-600">
            <AlertTriangle size={12} />
            {connectError}
          </p>
        )}
      </div>
    </div>
  )
}

// ── GitHub card ───────────────────────────────────────────────────────────────

function GitHubCard({
  workspaceId,
  integration,
}: {
  workspaceId: string
  integration: IntegrationStatus
}) {
  const connectMutation = useGitHubConnect(workspaceId)
  const disconnectMutation = useGitHubDisconnect(workspaceId)
  const isConnected = integration.connected && !integration.expired

  const connectError =
    connectMutation.isError
      ? ((connectMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
         "Could not start GitHub sign-in. Add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to server .env.")
      : null

  return (
    <div className="rounded-2xl border border-border/60 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <IntegrationBrandIcon provider="github" />
          <div>
            <p className="font-medium text-sm">GitHub</p>
            <p className="text-xs text-muted-foreground">Repos · Issues · PRs · Code search</p>
          </div>
        </div>
        <StatusBadge integration={integration} />
      </div>

      {isConnected && integration.account_email && (
        <div className="mt-4 rounded-xl bg-muted/40 px-3 py-2.5 text-xs space-y-1">
          <p>
            <span className="text-muted-foreground">Account:</span>{" "}
            <span className="font-medium">{integration.account_email}</span>
          </p>
          {integration.connected_at && (
            <p>
              <span className="text-muted-foreground">Connected:</span>{" "}
              {new Date(integration.connected_at).toLocaleDateString()}
            </p>
          )}
          <p className="text-muted-foreground pt-1">
            Org scope: set <code className="text-[10px]">GITHUB_DEFAULT_ORG=LNO360</code> on the API server to limit repos.
          </p>
        </div>
      )}

      <div className="mt-4 space-y-2">
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive border-destructive/30 hover:bg-red-50"
              onClick={() => disconnectMutation.mutate()}
              disabled={disconnectMutation.isPending}
            >
              <Trash2 size={13} className="mr-1.5" />
              {disconnectMutation.isPending ? "Disconnecting…" : "Disconnect"}
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => connectMutation.mutate()}
              disabled={connectMutation.isPending}
              className="bg-zinc-900 hover:bg-zinc-800 text-white"
            >
              <ExternalLink size={13} className="mr-1.5" />
              {connectMutation.isPending ? "Redirecting…" : "Connect GitHub"}
            </Button>
          )}
        </div>
        {connectError && (
          <p className="flex items-center gap-1.5 text-xs text-red-600">
            <AlertTriangle size={12} />
            {connectError}
          </p>
        )}
      </div>
    </div>
  )
}

// ── GitHub App (Webhooks) card ────────────────────────────────────────────────

function GitHubAppCard({
  workspaceId,
  appStatus,
}: {
  workspaceId: string
  appStatus: GithubAppStatus
}) {
  const installMutation   = useGitHubAppInstall(workspaceId)
  const uninstallMutation = useGitHubAppUninstall(workspaceId)

  return (
    <div className="mt-3 rounded-xl border border-dashed border-border/60 bg-muted/20 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">
            GitHub App{" "}
            <span className="text-xs text-muted-foreground">(Webhooks)</span>
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Auto-triggers Hermes on PRs, issues, pushes &amp; CI events
          </p>
        </div>
        {appStatus.installed ? (
          <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 shrink-0">
            <CheckCircle size={11} /> Installed
          </span>
        ) : (
          <span className="flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 shrink-0">
            <AlertTriangle size={11} /> Not installed
          </span>
        )}
      </div>

      {appStatus.installed && appStatus.account_login && (
        <p className="mt-2 text-xs text-muted-foreground">
          Organization:{" "}
          <span className="font-medium text-foreground">
            {appStatus.account_login}
          </span>
        </p>
      )}

      <div className="mt-3 flex gap-2">
        {appStatus.installed ? (
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs text-destructive border-destructive/30 hover:bg-destructive/10"
            onClick={() => uninstallMutation.mutate()}
            disabled={uninstallMutation.isPending}
          >
            {uninstallMutation.isPending ? (
              <Loader2 size={11} className="animate-spin mr-1" />
            ) : (
              <Trash2 size={11} className="mr-1" />
            )}
            Uninstall
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={() => installMutation.mutate()}
            disabled={installMutation.isPending}
          >
            {installMutation.isPending ? (
              <Loader2 size={11} className="animate-spin mr-1" />
            ) : (
              <ExternalLink size={11} className="mr-1" />
            )}
            Install GitHub App →
          </Button>
        )}
      </div>

      {installMutation.isError && (
        <p className="mt-2 text-xs text-destructive">
          {(installMutation.error as Error)?.message ??
            "Could not open install page. Ensure GITHUB_APP_NAME is set on the server."}
        </p>
      )}
    </div>
  )
}

// ── GitHub Events feed ────────────────────────────────────────────────────────

const EVENT_ICON: Record<string, React.ReactNode> = {
  pull_request: <GitPullRequest size={13} className="text-purple-500" />,
  issues:       <AlertCircle size={13} className="text-amber-500" />,
  push:         <Package size={13} className="text-blue-500" />,
  check_run:    <AlertCircle size={13} className="text-red-500" />,
}

const STATUS_CHIP: Record<string, string> = {
  done:       "bg-emerald-50 text-emerald-700",
  skipped:    "bg-muted text-muted-foreground",
  error:      "bg-red-50 text-red-700",
  processing: "bg-blue-50 text-blue-700",
  received:   "bg-muted text-muted-foreground",
}

function relativeTime(iso: string | null): string {
  if (!iso) return ""
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function GitHubEventsPanel({ workspaceId }: { workspaceId: string }) {
  const { data, isLoading } = useGitHubEvents(workspaceId, 10)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-4 text-xs text-muted-foreground">
        <Loader2 size={12} className="animate-spin" /> Loading events…
      </div>
    )
  }

  const events = data?.events ?? []
  if (events.length === 0) {
    return (
      <p className="py-4 text-xs text-muted-foreground">
        No events yet. Install the GitHub App and events will appear here.
      </p>
    )
  }

  return (
    <div className="mt-3 rounded-xl border border-border/60 bg-white overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border/60 flex items-center justify-between">
        <p className="text-xs font-medium">GitHub Events</p>
        <p className="text-xs text-muted-foreground">last 10</p>
      </div>
      <div className="divide-y divide-border/40">
        {events.map((e: GithubEventItem) => (
          <div key={e.id} className="flex items-center gap-3 px-4 py-2.5">
            <span className="shrink-0">
              {EVENT_ICON[e.event_type] ?? <GitBranch size={13} />}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">
                {e.event_type}{e.action ? ` · ${e.action}` : ""}
              </p>
              <p className="text-xs text-muted-foreground truncate">
                {e.repo_full_name}
              </p>
            </div>
            <span className="text-xs text-muted-foreground shrink-0">
              {relativeTime(e.received_at)}
            </span>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CHIP[e.status] ?? STATUS_CHIP.received}`}
            >
              {e.status === "skipped" ? (
                <><SkipForward size={9} className="inline mr-0.5" />skipped</>
              ) : (
                e.status
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Brave card ────────────────────────────────────────────────────────────────

function BraveCard({
  workspaceId,
  integration,
}: {
  workspaceId: string
  integration: IntegrationStatus
}) {
  const [apiKey, setApiKey] = useState("")
  const [show, setShow] = useState(false)
  const [editing, setEditing] = useState(!integration.key_set)
  const saveMutation = useSaveBraveKey(workspaceId)
  const removeMutation = useRemoveBraveKey(workspaceId)

  // Sync editing state when key_set changes (after save/remove)
  useEffect(() => {
    setEditing(!integration.key_set)
  }, [integration.key_set])

  async function handleSave() {
    if (!apiKey.trim()) return
    await saveMutation.mutateAsync(apiKey.trim())
    setApiKey("")
  }

  return (
    <div className="rounded-2xl border border-border/60 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border bg-orange-50 shadow-sm">
            <Globe size={18} className="text-orange-600" />
          </div>
          <div>
            <p className="font-medium text-sm">Web Search</p>
            <p className="text-xs text-muted-foreground">
              Brave Search API · web_search + web_fetch_page
            </p>
          </div>
        </div>
        <StatusBadge integration={integration} overrideConnected={!!integration.key_set} />
      </div>

      <div className="mt-4 space-y-3">
        {integration.key_set && !editing ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 rounded-lg border bg-muted/30 px-3 py-2 font-mono text-xs text-muted-foreground">
              ••••••••••••••••
            </div>
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => removeMutation.mutate()}
              disabled={removeMutation.isPending}
            >
              <Trash2 size={13} />
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="relative">
              <Input
                type={show ? "text" : "password"}
                placeholder="BSA••• (from api.search.brave.com)"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSave()}
                className="pr-10 font-mono text-sm"
              />
              <button
                onClick={() => setShow(s => !s)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {show ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={handleSave}
                disabled={!apiKey.trim() || saveMutation.isPending}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
              >
                {saveMutation.isPending ? "Saving…" : "Save key"}
              </Button>
              {integration.key_set && (
                <Button variant="outline" size="sm" onClick={() => setEditing(false)}>
                  Cancel
                </Button>
              )}
            </div>
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          Get a free key at{" "}
          <a
            href="https://api.search.brave.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 underline"
          >
            api.search.brave.com
          </a>{" "}
          — free tier gives 2,000 searches/month.
        </p>
      </div>
    </div>
  )
}

// ── Tool capability chips ─────────────────────────────────────────────────────

function ToolChips({ title, tools }: { title: string; tools: string[] }) {
  return (
    <div className="mt-2 rounded-2xl border border-border/60 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">
        {title}
      </p>
      <div className="flex flex-wrap gap-2">
        {tools.map(t => (
          <span
            key={t}
            className="rounded-lg border border-border/50 bg-muted/30 px-2.5 py-1 font-mono text-xs text-foreground/80"
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function IntegrationsTab({ workspaceId }: { workspaceId: string }) {
  const { data, isLoading } = useIntegrations(workspaceId)
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()

  const [justConnected, setJustConnected] = useState<string | null>(null)
  useEffect(() => {
    const provider = searchParams.get("connected")
    if (provider === "google" || provider === "github") {
      setJustConnected(provider)
      const t = setTimeout(() => setJustConnected(null), 5000)
      return () => clearTimeout(t)
    }
    if (provider === "github-app") {
      queryClient.invalidateQueries({ queryKey: ["integrations", workspaceId] })
    }
  }, [searchParams, queryClient, workspaceId])

  const google = data?.integrations.find(i => i.provider === "google") ?? {
    provider: "google" as const,
    connected: false,
  }
  const brave = data?.integrations.find(i => i.provider === "brave") ?? {
    provider: "brave" as const,
    connected: false,
  }
  const github = data?.integrations.find(i => i.provider === "github") ?? {
    provider: "github" as const,
    connected: false,
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-32 rounded-2xl border bg-muted/30 animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl space-y-4">
      <div>
        <h2 className="text-sm font-semibold">Integrations</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Connect Google Workspace, GitHub, and web search so Hermes can use them from chat and Telegram.
        </p>
      </div>

      {justConnected === "google" && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          ✓ Google Workspace connected successfully.
        </div>
      )}
      {justConnected === "github" && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          ✓ GitHub connected successfully.
        </div>
      )}

      <GoogleCard workspaceId={workspaceId} integration={google} />
      <GitHubCard workspaceId={workspaceId} integration={github} />

      {/* GitHub App + Events */}
      {data && (
        <>
          <GitHubAppCard
            workspaceId={workspaceId}
            appStatus={
              data.github_app ?? {
                installed: false,
                account_login: null,
                installation_id: null,
                installed_at: null,
              }
            }
          />
          {data.github_app?.installed && (
            <GitHubEventsPanel workspaceId={workspaceId} />
          )}
        </>
      )}

      <BraveCard workspaceId={workspaceId} integration={brave} />

      <GoogleHermesToolsPanel />

      <ToolChips
        title="GitHub tools"
        tools={[
          "github_list_repos",
          "github_list_issues",
          "github_get_issue",
          "github_list_prs",
          "github_get_pr",
          "github_search_code",
          "github_create_issue",
          "github_add_issue_comment",
        ]}
      />
      <ToolChips
        title="Web search"
        tools={["web_search", "web_fetch_page"]}
      />
    </div>
  )
}
