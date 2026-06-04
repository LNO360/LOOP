"use client"
import { useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { api } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { useInviteInfo } from "@/hooks/use-invite"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2 } from "lucide-react"

function SignupForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const inviteToken = searchParams.get("invite")
  const setAuth = useAuthStore((s) => s.setAuth)

  const { data: inviteInfo } = useInviteInfo(inviteToken)

  const [form, setForm] = useState({ email: "", password: "", name: "", workspace_name: "" })
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const isJoinFlow = !!inviteToken

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError("")
    try {
      const payload = isJoinFlow
        ? { email: form.email, password: form.password, name: form.name }
        : { ...form }
      const { data } = await api.post("/auth/signup", payload)
      const meRes = await api.get("/auth/me", { headers: { Authorization: `Bearer ${data.token}` } })

      let workspaceId: string = data.workspace_id ?? ""

      if (isJoinFlow && inviteToken) {
        try {
          const accepted = await api.post(
            `/invites/${inviteToken}/accept`,
            {},
            { headers: { Authorization: `Bearer ${data.token}` } }
          )
          workspaceId = accepted.data.workspace_id
        } catch { /* expired invite — continue anyway */ }
      }

      setAuth(data.token, meRes.data, workspaceId)
      // Always go through onboarding — owner gets full wizard, member gets profile+tools
      const flow = isJoinFlow ? "member" : workspaceId ? "owner" : "join"
      router.push(`/onboarding?flow=${flow}`)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail ?? "Something went wrong")
    } finally {
      setLoading(false)
    }
  }

  const field = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [key]: e.target.value })),
  })

  return (
    <Card>
      <CardHeader>
        {isJoinFlow && inviteInfo ? (
          <>
            <CardTitle>Join {inviteInfo.workspace_name}</CardTitle>
            <CardDescription>
              {inviteInfo.inviter_name} invited you · Create your account to join
            </CardDescription>
          </>
        ) : (
          <>
            <CardTitle>Create your workspace</CardTitle>
            <CardDescription>Get your team set up in minutes</CardDescription>
          </>
        )}
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label>Your name</Label>
            <Input placeholder="Jane Doe" required {...field("name")} />
          </div>
          <div className="space-y-1">
            <Label>Email</Label>
            <Input type="email" placeholder="you@company.com" required {...field("email")} />
          </div>
          <div className="space-y-1">
            <Label>Password</Label>
            <Input type="password" required {...field("password")} />
          </div>
          {!isJoinFlow && (
            <div className="space-y-1">
              <Label>Workspace name</Label>
              <Input placeholder="Acme Corp" required={!isJoinFlow} {...field("workspace_name")} />
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
            {isJoinFlow ? `Join ${inviteInfo?.workspace_name ?? "workspace"}` : "Create workspace"}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link
              href={inviteToken ? `/login?invite=${inviteToken}` : "/login"}
              className="text-foreground font-medium underline underline-offset-4 hover:opacity-80"
            >
              Sign in
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  )
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  )
}
