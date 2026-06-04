"use client"
import { useState, useEffect, useRef, useCallback, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useAuthStore } from "@/store/auth"
import { useCreateInviteLink, useInviteInfo, useAcceptInvite } from "@/hooks/use-invite"
import { useIntegrations, useGoogleConnect, useGitHubAppInstall } from "@/hooks/use-integrations"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Check, Copy, ExternalLink, Loader2 } from "lucide-react"

// ── Types ─────────────────────────────────────────────────────────────────

type Flow = "owner" | "member" | "join"

// Owner:  profile → workspace → invite → tools
// Member: profile → tools
// Join:   choose (create / join-with-link) → profile → tools

const OWNER_STEPS  = ["Your profile", "Workspace", "Invite team", "Connect tools"]
const MEMBER_STEPS = ["Your profile", "Connect tools"]
const JOIN_STEPS   = ["Get started", "Your profile", "Connect tools"]

// ── Helpers ───────────────────────────────────────────────────────────────

function stepsForFlow(flow: Flow) {
  if (flow === "owner")  return OWNER_STEPS
  if (flow === "member") return MEMBER_STEPS
  return JOIN_STEPS
}

// ── Sidebar step tracker ──────────────────────────────────────────────────

function StepTracker({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="w-64 bg-gray-50 border-l border-gray-200 flex flex-col justify-between py-10 px-6 shrink-0">
      <div className="space-y-1">
        {steps.map((label, i) => {
          const n = i + 1
          const done   = current > n
          const active = current === n
          return (
            <div key={label} className="flex gap-3 py-3">
              <div className="mt-0.5 shrink-0">
                {done ? (
                  <div className="h-5 w-5 rounded-full bg-blue-600 flex items-center justify-center">
                    <Check size={11} className="text-white" strokeWidth={3} />
                  </div>
                ) : (
                  <div className={cn(
                    "h-5 w-5 rounded-full border-2 flex items-center justify-center text-[10px] font-bold",
                    active ? "border-blue-600 text-blue-600 bg-white" : "border-gray-300 text-gray-400 bg-white"
                  )}>
                    {n}
                  </div>
                )}
              </div>
              <div>
                <div className={cn(
                  "text-sm font-semibold leading-tight",
                  done ? "text-gray-400 line-through" : active ? "text-gray-900" : "text-gray-400"
                )}>
                  {label}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Help card */}
      <div className="border border-gray-200 rounded-xl p-4 bg-white space-y-2">
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 rounded-full bg-gray-100 flex items-center justify-center text-gray-500 text-xs font-bold">?</div>
          <span className="text-xs font-semibold text-gray-700">Having trouble?</span>
        </div>
        <p className="text-xs text-gray-400 leading-relaxed">
          Contact us and we&apos;ll help you through the setup process.
        </p>
        <a
          href="mailto:support@lno.so"
          className="inline-block text-xs font-semibold border border-gray-200 rounded-md px-3 py-1.5 text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Contact us
        </a>
      </div>
    </div>
  )
}

// ── CTA buttons ───────────────────────────────────────────────────────────

function PrimaryBtn({ onClick, disabled, loading, children }: {
  onClick?: () => void; disabled?: boolean; loading?: boolean; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="w-full flex items-center justify-center gap-2 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
    >
      {loading && <Loader2 size={13} className="animate-spin" />}
      {children}
    </button>
  )
}

function BackBtn({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="w-full py-2 text-sm text-gray-400 hover:text-gray-600 transition-colors">
      Back
    </button>
  )
}

// ── Profile step ──────────────────────────────────────────────────────────

function ProfileStep({
  initialName,
  onNext,
}: {
  initialName: string
  onNext: (data: { name: string; phone: string; telegramUsername: string }) => Promise<void>
}) {
  const [name, setName]      = useState(initialName)
  const [phone, setPhone]    = useState("")
  const [tg, setTg]          = useState("")
  const [saving, setSaving]  = useState(false)
  const [error, setError]    = useState("")

  async function handleNext() {
    if (!name.trim()) { setError("Name is required"); return }
    setSaving(true)
    setError("")
    try {
      await onNext({ name: name.trim(), phone, telegramUsername: tg })
    } catch {
      setError("Failed to save. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="w-full max-w-sm space-y-7">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Your profile</h1>
        <p className="text-sm text-gray-500">Tell us a little about yourself so your team knows who you are.</p>
      </div>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Full name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Jane Doe"
            className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
            autoFocus
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Phone number <span className="normal-case font-normal text-gray-400">(optional)</span>
          </label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+1 555 000 0000"
            type="tel"
            className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Telegram handle <span className="normal-case font-normal text-gray-400">(optional)</span>
          </label>
          <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
            <span className="px-3 py-2.5 bg-gray-50 text-sm text-gray-400 border-r border-gray-200 select-none">@</span>
            <input
              value={tg}
              onChange={(e) => setTg(e.target.value.replace(/^@/, ""))}
              placeholder="yourhandle"
              className="flex-1 px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 outline-none bg-white"
            />
          </div>
          <p className="text-xs text-gray-400">Used to receive notifications and approvals via Telegram</p>
        </div>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      <PrimaryBtn onClick={handleNext} loading={saving} disabled={!name.trim()}>
        Continue
      </PrimaryBtn>
    </div>
  )
}

// ── Telegram Login Widget ─────────────────────────────────────────────────

const TG_BOT_NAME = "LNO_Founders_office_bot"

function TelegramLoginButton({ onConnected }: { onConnected: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const onConnectedRef = useRef(onConnected)
  useEffect(() => { onConnectedRef.current = onConnected }, [onConnected])
  const [error, setError] = useState("")

  useEffect(() => {
    if (!containerRef.current) return

    ;(window as Record<string, unknown>)["_tgWidgetAuth"] = async (user: Record<string, unknown>) => {
      setError("")
      try {
        await api.post("/auth/telegram-connect/widget", user)
        onConnectedRef.current()
      } catch {
        setError("Connection failed. Please try again.")
      }
    }

    const script = document.createElement("script")
    script.src = "https://telegram.org/js/telegram-widget.js?22"
    script.setAttribute("data-telegram-login", TG_BOT_NAME)
    script.setAttribute("data-size", "medium")
    script.setAttribute("data-onauth", "_tgWidgetAuth(user)")
    script.async = true
    containerRef.current.appendChild(script)

    return () => {
      delete (window as Record<string, unknown>)["_tgWidgetAuth"]
    }
  }, [])

  return (
    <div className="space-y-1.5">
      <div ref={containerRef} />
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}

// ── Tools step ────────────────────────────────────────────────────────────

function ToolsStep({
  workspaceId,
  onFinish,
  onBack,
}: {
  workspaceId: string
  onFinish: () => void
  onBack: () => void
}) {
  const { data: integrations } = useIntegrations(workspaceId)
  const googleConnect  = useGoogleConnect(workspaceId)
  const githubInstall  = useGitHubAppInstall(workspaceId)

  const [tgConnected, setTgConnected] = useState(false)

  const googleConnected = integrations?.integrations?.find((i) => i.provider === "google")?.connected ?? false
  const githubConnected = integrations?.github_app?.installed ?? false

  const anyConnected = googleConnected || githubConnected || tgConnected

  return (
    <div className="w-full max-w-sm space-y-7">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Connect your tools</h1>
        <p className="text-sm text-gray-500">
          Hermes can read your emails, calendar, repos, and message you on Telegram.
        </p>
      </div>

      <div className="space-y-2.5">
        {/* Google */}
        <IntegrationRow
          icon={<span className="text-sm font-bold text-gray-700">G</span>}
          name="Google Workspace"
          sub="Gmail · Calendar · Drive"
          connected={googleConnected}
          onConnect={() => googleConnect.mutate()}
          connecting={googleConnect.isPending}
          label="Connect"
        />

        {/* GitHub */}
        <IntegrationRow
          icon={<GithubIcon />}
          name="GitHub App"
          sub="Pull requests · Issues · CI"
          connected={githubConnected}
          onConnect={() => githubInstall.mutate()}
          connecting={githubInstall.isPending}
          label="Install"
          labelIcon={<ExternalLink size={11} />}
        />

        {/* Telegram */}
        <div className={cn(
          "rounded-lg border-2 transition-all overflow-hidden",
          tgConnected ? "border-green-200 bg-green-50" : "border-gray-200"
        )}>
          <div className="flex items-center gap-3 px-4 py-3.5">
            <div className="w-8 h-8 rounded-md bg-white border border-gray-200 flex items-center justify-center shrink-0 shadow-sm">
              <TelegramIcon />
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-gray-900">Telegram</div>
              <div className="text-xs text-gray-400">Receive approvals and alerts</div>
            </div>
            {tgConnected && (
              <span className="flex items-center gap-1 text-xs font-semibold text-green-700">
                <Check size={13} /> Connected
              </span>
            )}
          </div>

          {!tgConnected && (
            <div className="border-t border-gray-200 px-4 py-3 bg-white space-y-2">
              <p className="text-xs text-gray-500">Tap the button below to connect your Telegram account.</p>
              <TelegramLoginButton onConnected={() => setTgConnected(true)} />
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2 pt-1">
        <PrimaryBtn onClick={onFinish}>
          {anyConnected ? "Go to workspace" : "Skip for now"}
        </PrimaryBtn>
        <BackBtn onClick={onBack} />
      </div>
    </div>
  )
}

function IntegrationRow({
  icon, name, sub, connected, onConnect, connecting, label, labelIcon
}: {
  icon: React.ReactNode; name: string; sub: string
  connected: boolean; onConnect: () => void; connecting: boolean
  label: string; labelIcon?: React.ReactNode
}) {
  return (
    <div className={cn(
      "flex items-center gap-3 px-4 py-3.5 rounded-lg border-2 transition-all",
      connected ? "border-green-200 bg-green-50" : "border-gray-200"
    )}>
      <div className="w-8 h-8 rounded-md bg-white border border-gray-200 flex items-center justify-center shrink-0 shadow-sm">
        {icon}
      </div>
      <div className="flex-1">
        <div className="text-sm font-semibold text-gray-900">{name}</div>
        <div className="text-xs text-gray-400">{sub}</div>
      </div>
      {connected ? (
        <span className="flex items-center gap-1 text-xs font-semibold text-green-700">
          <Check size={13} /> Connected
        </span>
      ) : (
        <button
          onClick={onConnect}
          disabled={connecting}
          className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-40"
        >
          {connecting ? <Loader2 size={12} className="animate-spin" /> : <>{labelIcon}{label}</>}
        </button>
      )}
    </div>
  )
}

function GithubIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-4 h-4 fill-gray-800">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
    </svg>
  )
}

function TelegramIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-4 h-4 fill-blue-500">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
    </svg>
  )
}

// ── Join flow — choose or enter invite ────────────────────────────────────

function JoinStep({
  onCreateWorkspace,
  onJoined,
}: {
  onCreateWorkspace: () => void
  onJoined: (workspaceId: string) => void
}) {
  const [mode, setMode]       = useState<"choose" | "invite">("choose")
  const [inviteInput, setInviteInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState("")
  const acceptInvite = useAcceptInvite()

  // Extract token from full URL or plain token
  function extractToken(val: string): string {
    try {
      const url = new URL(val)
      const parts = url.pathname.split("/join/")
      if (parts[1]) return parts[1].trim()
    } catch { /* not a URL */ }
    return val.trim()
  }

  async function handleJoinInvite() {
    const token = extractToken(inviteInput)
    if (!token) { setError("Paste your invite link or code"); return }
    setLoading(true)
    setError("")
    try {
      const result = await acceptInvite.mutateAsync(token)
      onJoined(result.workspace_id)
    } catch {
      setError("Invalid or expired invite link. Ask your teammate for a new one.")
    } finally {
      setLoading(false)
    }
  }

  if (mode === "choose") {
    return (
      <div className="w-full max-w-sm space-y-7">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Get started</h1>
          <p className="text-sm text-gray-500">Are you creating a new workspace or joining an existing one?</p>
        </div>

        <div className="space-y-3">
          <button
            onClick={onCreateWorkspace}
            className="w-full text-left p-4 rounded-xl border-2 border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group"
          >
            <div className="text-sm font-semibold text-gray-900 group-hover:text-blue-700">Create a new workspace</div>
            <div className="text-xs text-gray-400 mt-0.5">You are the owner — set it up for your team</div>
          </button>

          <button
            onClick={() => setMode("invite")}
            className="w-full text-left p-4 rounded-xl border-2 border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group"
          >
            <div className="text-sm font-semibold text-gray-900 group-hover:text-blue-700">Join with an invite link</div>
            <div className="text-xs text-gray-400 mt-0.5">Your teammate shared a link — paste it here</div>
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-sm space-y-7">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Join a workspace</h1>
        <p className="text-sm text-gray-500">Paste the invite link your teammate sent you.</p>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Invite link</label>
        <input
          value={inviteInput}
          onChange={(e) => setInviteInput(e.target.value)}
          placeholder="https://app.lno.so/join/abc123..."
          className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
          autoFocus
        />
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>

      <div className="space-y-2">
        <PrimaryBtn onClick={handleJoinInvite} loading={loading} disabled={!inviteInput.trim()}>
          Join workspace
        </PrimaryBtn>
        <BackBtn onClick={() => setMode("choose")} />
      </div>
    </div>
  )
}

// ── Workspace step (owner: name their workspace) ──────────────────────────

function WorkspaceStep({
  initialName,
  workspaceId,
  onNext,
  onBack,
}: {
  initialName: string
  workspaceId: string | null
  onNext: (newWorkspaceId: string) => void
  onBack: () => void
}) {
  const [name, setName]       = useState(initialName)
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState("")

  async function handleNext() {
    if (!name.trim()) { setError("Please enter a workspace name"); return }
    setSaving(true)
    try {
      if (workspaceId) {
        // Existing workspace — just rename it
        const { data } = await api.patch(`/workspaces/${workspaceId}`, { name: name.trim() })
        onNext(data.id)
      } else {
        // No workspace yet — create one
        const { data } = await api.post("/workspaces", { name: name.trim() })
        onNext(data.id)
      }
    } catch {
      setError("Failed to save. Try again.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="w-full max-w-sm space-y-7">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Name your workspace</h1>
        <p className="text-sm text-gray-500">This is the name your team will see when they log in.</p>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Workspace name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Acme Corp"
          className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
          onKeyDown={(e) => { if (e.key === "Enter") handleNext() }}
          autoFocus
        />
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>

      <div className="space-y-2">
        <PrimaryBtn onClick={handleNext} loading={saving} disabled={!name.trim()}>
          Continue
        </PrimaryBtn>
        <BackBtn onClick={onBack} />
      </div>
    </div>
  )
}

// ── Invite step (owner: generate shareable link) ──────────────────────────

function InviteStep({
  workspaceId,
  wsName,
  onNext,
  onBack,
}: {
  workspaceId: string
  wsName: string
  onNext: () => void
  onBack: () => void
}) {
  const [inviteUrl, setInviteUrl] = useState("")
  const [copied, setCopied]       = useState(false)
  const createInviteLink = useCreateInviteLink(workspaceId)

  async function generate() {
    try { const r = await createInviteLink.mutateAsync(); setInviteUrl(r.url) }
    catch { /* ignore */ }
  }

  function copy() {
    navigator.clipboard.writeText(inviteUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="w-full max-w-sm space-y-7">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Invite your team</h1>
        <p className="text-sm text-gray-500">Share this link — anyone with it can join {wsName}.</p>
      </div>

      <div className="space-y-3">
        {!inviteUrl ? (
          <button
            onClick={generate}
            disabled={createInviteLink.isPending}
            className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm font-medium text-gray-500 hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all disabled:opacity-40"
          >
            {createInviteLink.isPending ? "Generating…" : "Generate invite link"}
          </button>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2.5 bg-gray-50">
              <span className="flex-1 text-xs font-mono text-gray-500 truncate">{inviteUrl}</span>
              <button
                onClick={copy}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-semibold shrink-0 transition-all",
                  copied ? "bg-green-100 text-green-700" : "bg-blue-600 text-white hover:bg-blue-700"
                )}
              >
                {copied ? <><Check size={11} /> Copied</> : <><Copy size={11} /> Copy link</>}
              </button>
            </div>
            <p className="text-xs text-gray-400 text-center">Expires in 7 days · Anyone with the link can join</p>
          </div>
        )}
      </div>

      <div className="space-y-2">
        <PrimaryBtn onClick={onNext}>{inviteUrl ? "Continue" : "Skip for now"}</PrimaryBtn>
        <BackBtn onClick={onBack} />
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────

function OnboardingInner() {
  const searchParams = useSearchParams()
  const router       = useRouter()
  const authStore    = useAuthStore()
  const { user, workspaceId, setAuth, token: authToken } = authStore

  // Detect flow from URL param, falling back to store state
  const flowParam = (searchParams.get("flow") ?? "") as Flow | ""
  const [flow, setFlow] = useState<Flow>(() => {
    if (flowParam === "member") return "member"
    if (flowParam === "owner")  return "owner"
    if (workspaceId)             return "owner"
    return "join"
  })

  const steps   = stepsForFlow(flow)
  const [step, setStep] = useState(1)           // 1-indexed within flow's steps
  const [wsName, setWsName] = useState("")

  const totalSteps = steps.length

  // Load workspace name for display
  useEffect(() => {
    if (!workspaceId) return
    api.get(`/workspaces/${workspaceId}`)
      .then((r) => setWsName(r.data.name ?? ""))
      .catch(() => {})
  }, [workspaceId])

  // ── Profile save ──────────────────────────────────────────────────────

  async function saveProfile(data: { name: string; phone: string; telegramUsername: string }) {
    await api.patch("/auth/profile", {
      name: data.name,
      phone: data.phone || null,
      telegram_username: data.telegramUsername || null,
    })
    // Refresh user in store
    const me = await api.get("/auth/me")
    if (authToken) setAuth(authToken, me.data, workspaceId ?? "")
    setStep((s) => s + 1)
  }

  // ── Finish ────────────────────────────────────────────────────────────

  function finish() {
    if (workspaceId) router.push(`/workspace/${workspaceId}`)
    else router.push("/onboarding?flow=join")
  }

  // ── Join flow: after joining, switch to member flow ───────────────────

  function handleJoined(wsId: string) {
    if (authToken && user) setAuth(authToken, user, wsId)
    setFlow("member")
    setStep(1)
  }

  // ── Render ────────────────────────────────────────────────────────────

  function renderStep() {
    // JOIN flow
    if (flow === "join") {
      if (step === 1) return (
        <JoinStep
          onCreateWorkspace={() => { setFlow("owner"); setStep(1) }}
          onJoined={handleJoined}
        />
      )
    }

    // OWNER flow
    if (flow === "owner") {
      if (step === 1) return (
        <ProfileStep
          initialName={user?.name ?? ""}
          onNext={saveProfile}
        />
      )
      if (step === 2) return (
        <WorkspaceStep
          initialName={wsName}
          workspaceId={workspaceId ?? null}
          onNext={(newId) => {
            // If a new workspace was created, update auth store
            if (!workspaceId && authToken && user) setAuth(authToken, user, newId)
            setStep(3)
          }}
          onBack={() => setStep(1)}
        />
      )
      if (step === 3) return (
        <InviteStep
          workspaceId={workspaceId ?? ""}
          wsName={wsName}
          onNext={() => setStep(4)}
          onBack={() => setStep(2)}
        />
      )
      if (step === 4) return (
        <ToolsStep
          workspaceId={workspaceId ?? ""}
          onFinish={finish}
          onBack={() => setStep(3)}
        />
      )
    }

    // MEMBER flow
    if (flow === "member") {
      if (step === 1) return (
        <ProfileStep
          initialName={user?.name ?? ""}
          onNext={saveProfile}
        />
      )
      if (step === 2) return (
        <ToolsStep
          workspaceId={workspaceId ?? ""}
          onFinish={finish}
          onBack={() => setStep(1)}
        />
      )
    }

    // Fallback
    finish()
    return null
  }

  return (
    <div className="min-h-screen bg-[#f4f4f5] flex items-center justify-center p-6">
      <div className="w-full max-w-4xl bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden flex min-h-[520px]">

        {/* Content */}
        <div className="flex-1 flex flex-col items-center justify-center px-10 py-12">
          {renderStep()}
        </div>

        {/* Step tracker */}
        <StepTracker steps={steps} current={step} />
      </div>
    </div>
  )
}

export default function OnboardingPage() {
  return (
    <Suspense>
      <OnboardingInner />
    </Suspense>
  )
}
