"use client"
import { use, useState, useEffect } from "react"
import { Settings, Trash2, UserCircle2, Mail, Link2, Copy, Check, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuthStore } from "@/store/auth"
import {
  useWorkspace,
  useUpdateWorkspace,
  useWorkspaceMembers,
  useRemoveMember,
} from "@/hooks/use-workspace"
import { useCreateInviteLink } from "@/hooks/use-invite"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

interface PageProps {
  params: Promise<{ workspaceId: string }>
}

const roleColors: Record<string, string> = {
  owner: "bg-violet-500/10 text-violet-600",
  admin: "bg-blue-500/10 text-blue-600",
  member: "bg-slate-500/10 text-slate-600",
}

export default function WorkspaceSettingsPage({ params }: PageProps) {
  const { workspaceId } = use(params)
  const currentUser = useAuthStore((s) => s.user)
  const qc = useQueryClient()

  // Workspace data
  const { data: workspace, isLoading: wsLoading } = useWorkspace(workspaceId)
  const updateWorkspace = useUpdateWorkspace(workspaceId)

  // Members data
  const { data: members = [], isLoading: membersLoading } = useWorkspaceMembers(workspaceId)
  const removeMember = useRemoveMember(workspaceId)

  // Invite
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")
  const invite = useMutation({
    mutationFn: ({ email, role }: { email: string; role: string }) =>
      api.post(`/workspaces/${workspaceId}/invite`, { email, role }).then((r) => r.data),
    onSuccess: () => {
      setInviteEmail("")
      qc.invalidateQueries({ queryKey: ["members", workspaceId] })
    },
  })

  // Invite link
  const createInviteLink = useCreateInviteLink(workspaceId)
  const [inviteUrl, setInviteUrl] = useState("")
  const [inviteCopied, setInviteCopied] = useState(false)

  async function generateLink(force = false) {
    if (inviteUrl && !force) return
    try {
      const r = await createInviteLink.mutateAsync()
      setInviteUrl(r.url)
    } catch { /* ignore */ }
  }

  function copyInviteLink() {
    navigator.clipboard.writeText(inviteUrl)
    setInviteCopied(true)
    setTimeout(() => setInviteCopied(false), 2000)
  }

  // General form
  const [workspaceName, setWorkspaceName] = useState("")
  useEffect(() => {
    if (workspace?.name) setWorkspaceName(workspace.name)
  }, [workspace?.name])

  const handleSaveName = (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspaceName.trim()) return
    updateWorkspace.mutate(workspaceName.trim())
  }

  return (
    <div className="p-6 max-w-3xl space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-accent/10 flex items-center justify-center">
          <Settings size={18} className="text-accent" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">Workspace Settings</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage your workspace name, members, and invitations
          </p>
        </div>
      </div>

      {/* General Section */}
      <section className="rounded-xl border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b">
          <h2 className="text-sm font-semibold">General</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Update your workspace display name</p>
        </div>
        <div className="px-5 py-5">
          {wsLoading ? (
            <div className="h-9 w-64 bg-muted animate-pulse rounded-md" />
          ) : (
            <form onSubmit={handleSaveName} className="flex items-center gap-3">
              <input
                type="text"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="Workspace name"
                className={cn(
                  "flex-1 max-w-xs h-9 rounded-md border bg-background px-3 text-sm",
                  "focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent",
                  "transition-colors placeholder:text-muted-foreground"
                )}
              />
              <button
                type="submit"
                disabled={updateWorkspace.isPending || !workspaceName.trim()}
                className={cn(
                  "h-9 px-4 rounded-md text-sm font-medium transition-colors",
                  "bg-accent text-accent-foreground hover:bg-accent/90",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              >
                {updateWorkspace.isPending ? "Saving…" : "Save"}
              </button>
              {updateWorkspace.isSuccess && (
                <span className="text-xs text-emerald-600">Saved</span>
              )}
              {updateWorkspace.isError && (
                <span className="text-xs text-red-500">Failed to save</span>
              )}
            </form>
          )}
        </div>
      </section>

      {/* Members Section */}
      <section className="rounded-xl border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b">
          <h2 className="text-sm font-semibold">Members</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {membersLoading ? "Loading…" : `${members.length} member${members.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <div className="divide-y">
          {membersLoading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-5 py-3.5">
                <div className="h-8 w-8 rounded-full bg-muted animate-pulse" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 w-32 bg-muted animate-pulse rounded" />
                  <div className="h-2.5 w-48 bg-muted animate-pulse rounded" />
                </div>
              </div>
            ))
          ) : members.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-muted-foreground">
              No members found
            </div>
          ) : (
            members.map((member) => {
              const isSelf = member.id === currentUser?.id
              return (
                <div key={member.id} className="flex items-center gap-3 px-5 py-3.5">
                  {/* Avatar */}
                  {member.avatar_url ? (
                    <img
                      src={member.avatar_url}
                      alt={member.name}
                      className="h-8 w-8 rounded-full object-cover shrink-0"
                    />
                  ) : (
                    <div className="h-8 w-8 rounded-full bg-accent/10 flex items-center justify-center shrink-0">
                      <UserCircle2 size={16} className="text-accent" />
                    </div>
                  )}

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">{member.name}</span>
                      {isSelf && (
                        <span className="text-xs text-muted-foreground">(you)</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1 mt-0.5">
                      <Mail size={11} className="text-muted-foreground shrink-0" />
                      <span className="text-xs text-muted-foreground truncate">
                        {member.email}
                      </span>
                    </div>
                  </div>

                  {/* Role chip */}
                  <span
                    className={cn(
                      "text-xs font-medium px-2 py-0.5 rounded-full capitalize",
                      roleColors[member.role] ?? roleColors["member"]
                    )}
                  >
                    {member.role}
                  </span>

                  {/* Remove button */}
                  <button
                    onClick={() => removeMember.mutate(member.id)}
                    disabled={isSelf || removeMember.isPending}
                    title={isSelf ? "Cannot remove yourself" : `Remove ${member.name}`}
                    className={cn(
                      "h-7 w-7 rounded-md flex items-center justify-center transition-colors",
                      isSelf
                        ? "opacity-30 cursor-not-allowed"
                        : "text-muted-foreground hover:text-red-500 hover:bg-red-500/10"
                    )}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              )
            })
          )}
        </div>
      </section>

      {/* Invite Link Section */}
      <section className="rounded-xl border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b">
          <div className="flex items-center gap-2">
            <Link2 size={15} className="text-accent" />
            <h2 className="text-sm font-semibold">Invite Link</h2>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Share this link — anyone with it can join your workspace
          </p>
        </div>
        <div className="px-5 py-5 space-y-3">
          {!inviteUrl ? (
            <button
              onClick={() => generateLink()}
              disabled={createInviteLink.isPending}
              className={cn(
                "flex items-center gap-2 h-9 px-4 rounded-md text-sm font-medium transition-colors",
                "bg-accent text-accent-foreground hover:bg-accent/90 disabled:opacity-50"
              )}
            >
              {createInviteLink.isPending ? (
                <><span className="animate-spin inline-block h-3 w-3 border-2 border-current border-t-transparent rounded-full" /> Generating…</>
              ) : (
                <><Link2 size={14} /> Generate invite link</>
              )}
            </button>
          ) : (
            <div className="space-y-2">
              <div className={cn(
                "flex items-center gap-3 border rounded-lg px-3 py-2.5 bg-muted/40"
              )}>
                <span className="flex-1 text-xs font-mono text-muted-foreground truncate">{inviteUrl}</span>
                <button
                  onClick={copyInviteLink}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all shrink-0",
                    inviteCopied
                      ? "bg-emerald-500/10 text-emerald-600"
                      : "bg-accent/10 text-accent hover:bg-accent/20"
                  )}
                >
                  {inviteCopied ? <><Check size={12} /> Copied!</> : <><Copy size={12} /> Copy</>}
                </button>
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">Expires in 7 days · Anyone with the link can join</p>
                <button
                  onClick={() => generateLink(true)}
                  disabled={createInviteLink.isPending}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  title="Generate a new link (invalidates current)"
                >
                  <RefreshCw size={11} /> New link
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Invite by email Section */}
      <section className="rounded-xl border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b">
          <h2 className="text-sm font-semibold">Invite Member</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Invite someone to this workspace by email
          </p>
        </div>
        <div className="px-5 py-5">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!inviteEmail.trim()) return
              invite.mutate({ email: inviteEmail.trim(), role: inviteRole })
            }}
            className="flex items-center gap-3 flex-wrap"
          >
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@example.com"
              className={cn(
                "flex-1 min-w-48 max-w-xs h-9 rounded-md border bg-background px-3 text-sm",
                "focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent",
                "transition-colors placeholder:text-muted-foreground"
              )}
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              className={cn(
                "h-9 rounded-md border bg-background px-2 text-sm",
                "focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
              )}
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
            <button
              type="submit"
              disabled={invite.isPending || !inviteEmail.trim()}
              className={cn(
                "h-9 px-4 rounded-md text-sm font-medium transition-colors",
                "bg-accent text-accent-foreground hover:bg-accent/90",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {invite.isPending ? "Inviting…" : "Invite"}
            </button>
            {invite.isSuccess && (
              <span className="text-xs text-emerald-600">Invited successfully</span>
            )}
            {invite.isError && (
              <span className="text-xs text-red-500">
                {(invite.error as { response?: { data?: { detail?: string } } })?.response?.data
                  ?.detail ?? "Failed to invite"}
              </span>
            )}
          </form>
        </div>
      </section>
    </div>
  )
}
