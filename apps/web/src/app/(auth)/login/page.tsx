"use client"
import { useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { api } from "@/lib/api"
import { useAuthStore } from "@/store/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2 } from "lucide-react"

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const inviteToken = searchParams.get("invite")
  const setAuth = useAuthStore((s) => s.setAuth)
  const [form, setForm] = useState({ email: "", password: "" })
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError("")
    try {
      const { data } = await api.post("/auth/login", form)
      const meRes = await api.get("/auth/me", { headers: { Authorization: `Bearer ${data.token}` } })
      let workspaceId: string = data.workspace_id ?? ""

      if (inviteToken) {
        try {
          const accepted = await api.post(
            `/invites/${inviteToken}/accept`,
            {},
            { headers: { Authorization: `Bearer ${data.token}` } }
          )
          workspaceId = accepted.data.workspace_id
        } catch { /* already member or expired — use existing workspace */ }
      }

      setAuth(data.token, meRes.data, workspaceId)
      router.push(workspaceId ? `/workspace/${workspaceId}` : "/onboarding")
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail ?? "Invalid credentials")
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
        <CardTitle>Welcome back</CardTitle>
        <CardDescription>
          {inviteToken ? "Sign in to accept your invitation" : "Sign in to your workspace"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label>Email</Label>
            <Input type="email" placeholder="you@company.com" required {...field("email")} />
          </div>
          <div className="space-y-1">
            <Label>Password</Label>
            <Input type="password" required {...field("password")} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
            Sign in
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link
              href={inviteToken ? `/signup?invite=${inviteToken}` : "/signup"}
              className="text-foreground font-medium underline underline-offset-4 hover:opacity-80"
            >
              Create one
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
