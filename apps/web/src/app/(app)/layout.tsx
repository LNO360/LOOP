"use client"

import { useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import { useAuthHydrated } from "@/hooks/use-auth-hydrated"
import { useAuthStore } from "@/store/auth"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const hasHydrated = useAuthHydrated()
  const token = useAuthStore((s) => s.token)
  const pathname = usePathname()
  const router = useRouter()

  const requiresAuth = pathname?.startsWith("/workspace/") ?? false

  useEffect(() => {
    if (!hasHydrated || !requiresAuth) return
    if (!token) router.replace("/login")
  }, [hasHydrated, requiresAuth, token, router])

  if (!hasHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (requiresAuth && !token) return null

  return <>{children}</>
}
