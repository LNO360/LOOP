// apps/web/src/app/(app)/join/[token]/page.tsx
"use client"
import { use, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useInviteInfo, useAcceptInvite } from "@/hooks/use-invite"
import { useAuthStore } from "@/store/auth"
import { Link2, Loader2, Users } from "lucide-react"

export default function JoinPage({ params }: { params: Promise<{ token: string }> }) {
  const resolvedParams = use(params)
  const { token } = resolvedParams
  const router = useRouter()
  const { token: authToken } = useAuthStore()
  const { data: invite, isLoading, isError } = useInviteInfo(token)
  const accept = useAcceptInvite()

  // If already logged in, auto-accept and navigate
  useEffect(() => {
    if (!authToken || !invite) return
    accept.mutate(token, {
      onSuccess: ({ workspace_id }) => {
        router.replace(`/workspace/${workspace_id}`)
      },
    })
  }, [authToken, invite]) // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    )
  }

  if (isError || !invite) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="text-center space-y-3">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-2xl bg-muted/60">
            <Link2 size={18} className="text-muted-foreground" />
          </div>
          <h1 className="text-lg font-semibold">Invite link invalid or expired</h1>
          <p className="text-sm text-muted-foreground">Ask your teammate to send a new one.</p>
          <Link href="/login" className="text-sm text-accent hover:underline">
            Sign in instead
          </Link>
        </div>
      </div>
    )
  }

  // Not logged in — show join card
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        {/* Workspace card */}
        <div className="bg-card border rounded-2xl p-8 text-center shadow-sm space-y-4">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">
              You&apos;re invited to
            </p>
            <h1 className="text-2xl font-bold">{invite.workspace_name}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              <span className="font-medium text-foreground">{invite.inviter_name}</span> invited you
            </p>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <div className="h-8 w-8 rounded-full bg-accent/10 flex items-center justify-center">
              <Users size={14} className="text-accent" />
            </div>
            <p className="text-sm text-muted-foreground">Join your team on Loop</p>
          </div>
        </div>

        {/* CTA buttons */}
        <div className="space-y-3">
          <Link
            href={`/signup?invite=${token}`}
            className="block w-full text-center py-3 bg-accent text-accent-foreground rounded-xl text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Create account
          </Link>
          <Link
            href={`/login?invite=${token}`}
            className="block w-full text-center py-3 border rounded-xl text-sm font-medium hover:bg-muted/50 transition-colors"
          >
            Sign in
          </Link>
        </div>

        <p className="text-center text-xs text-muted-foreground">
          By joining, you agree to the workspace rules set by its owner.
        </p>
      </div>
    </div>
  )
}
