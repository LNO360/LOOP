"use client"
import Link from "next/link"
import { AlertCircle, Plug } from "lucide-react"
import type { SeoOverview } from "@/hooks/use-seo"

interface IntegrationBannerProps {
  workspaceId: string
  overview?: SeoOverview
  siteUrl?: string | null
  siteReady?: boolean
}

export function IntegrationBanner({
  workspaceId,
  overview,
  siteUrl,
  siteReady = true,
}: IntegrationBannerProps) {
  if (!overview) return null

  const banners: { message: string; action?: string; href?: string }[] = []

  if (!overview.google_connected) {
    banners.push({
      message: "Connect Google to access Search Console analytics and URL inspection.",
      action: "Connect Google",
      href: `/workspace/${workspaceId}/settings?tab=integrations`,
    })
  } else if (
    siteReady &&
    !siteUrl &&
    overview.gsc.available === false &&
    overview.gsc.reason?.includes("property selected")
  ) {
    banners.push({
      message: "Select a Search Console property in the header dropdown.",
    })
  } else if (
    siteReady &&
    siteUrl &&
    overview.gsc.available === false &&
    overview.gsc.reason &&
    !overview.gsc.reason.includes("property selected")
  ) {
    banners.push({
      message: overview.gsc.reason,
      action: overview.gsc.reason.includes("Reconnect") || overview.gsc.reason.includes("denied")
        ? "Reconnect Google"
        : undefined,
      href: `/workspace/${workspaceId}/settings?tab=integrations`,
    })
  }

  if (!overview.blog_configured) {
    banners.push({
      message: "Blog CMS not configured. Set LNO_SITE_SUPABASE_URL on the API server.",
    })
  }

  if (banners.length === 0) return null

  return (
    <div className="space-y-2">
      {banners.map((b) => (
        <div
          key={b.message}
          className="flex items-center justify-between gap-4 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3"
        >
          <div className="flex items-start gap-2 text-sm text-amber-900 dark:text-amber-100">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            <span>{b.message}</span>
          </div>
          {b.action && b.href && (
            <Link
              href={b.href}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-muted"
            >
              <Plug size={14} />
              {b.action}
            </Link>
          )}
        </div>
      ))}
    </div>
  )
}
