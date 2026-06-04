"use client"
import { use } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard, Search, FileText, Wrench, Bot,
} from "lucide-react"
import { GscSitePicker, useGscSiteSelection } from "@/components/seo/gsc-site-picker"
import { SeoProvider } from "@/components/seo/seo-context"

const tabs = [
  { href: "", label: "Overview", icon: LayoutDashboard },
  { href: "/search", label: "Search", icon: Search },
  { href: "/content", label: "Content", icon: FileText },
  { href: "/technical", label: "Technical", icon: Wrench },
  { href: "/assistant", label: "Assistant", icon: Bot },
]

export default function SeoLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = use(params)
  const pathname = usePathname()
  const base = `/workspace/${workspaceId}/seo`
  const { siteUrl, selectSite, ready: siteReady } = useGscSiteSelection(workspaceId)

  return (
    <SeoProvider workspaceId={workspaceId} siteUrl={siteUrl} siteReady={siteReady} selectSite={selectSite}>
      <div className="flex flex-col h-full">
        <div className="border-b border-border/60 bg-background px-6 pt-5 pb-0">
          <div className="flex items-center justify-between gap-4 mb-3">
            <h1 className="text-lg font-semibold">SEO Analyst</h1>
            <GscSitePicker
              workspaceId={workspaceId}
              value={siteUrl}
              onChange={selectSite}
            />
          </div>
          <div className="flex items-center gap-1">
            {tabs.map(({ href, label, icon: Icon }) => {
              const fullHref = `${base}${href}`
              const active = href === ""
                ? pathname === base
                : pathname.startsWith(fullHref)
              return (
                <Link
                  key={href}
                  href={fullHref}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
                    active
                      ? "border-foreground text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon size={14} />
                  {label}
                </Link>
              )
            })}
          </div>
        </div>
        <div className="flex-1 overflow-auto">
          {children}
        </div>
      </div>
    </SeoProvider>
  )
}
