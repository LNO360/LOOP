"use client"
import { useEffect, useState } from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { useGscSites, getStoredGscSite, setStoredGscSite } from "@/hooks/use-seo"

interface GscSitePickerProps {
  workspaceId: string
  value: string | null
  onChange: (siteUrl: string) => void
  className?: string
}

export function GscSitePicker({ workspaceId, value, onChange, className }: GscSitePickerProps) {
  const { data, isLoading } = useGscSites(workspaceId)
  const sites = data?.sites ?? []

  useEffect(() => {
    if (!value && sites.length > 0) {
      const stored = getStoredGscSite(workspaceId)
      const match = sites.find((s) => s.siteUrl === stored)
      onChange(match?.siteUrl ?? sites[0].siteUrl)
    }
  }, [sites, value, workspaceId, onChange])

  const handleChange = (siteUrl: string) => {
    setStoredGscSite(workspaceId, siteUrl)
    onChange(siteUrl)
  }

  if (isLoading) {
    return <span className="text-xs text-muted-foreground">Loading properties…</span>
  }

  if (sites.length === 0) {
    return <span className="text-xs text-muted-foreground">No GSC properties</span>
  }

  return (
    <div className={cn("relative", className)}>
      <select
        value={value ?? ""}
        onChange={(e) => handleChange(e.target.value)}
        className="appearance-none rounded-lg border border-border/60 bg-background pl-3 pr-8 py-1.5 text-xs font-medium outline-none focus:ring-1 focus:ring-ring"
      >
        {sites.map((s) => (
          <option key={s.siteUrl} value={s.siteUrl}>
            {s.siteUrl}
          </option>
        ))}
      </select>
      <ChevronDown size={14} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
    </div>
  )
}

/** Hook to manage GSC site selection with localStorage persistence. */
export function useGscSiteSelection(workspaceId: string) {
  const [siteUrl, setSiteUrl] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  // Read localStorage after mount — SSR/hydration leaves useState(null) otherwise.
  useEffect(() => {
    const stored = getStoredGscSite(workspaceId)
    if (stored) setSiteUrl(stored)
    setReady(true)
  }, [workspaceId])

  const selectSite = (url: string) => {
    setStoredGscSite(workspaceId, url)
    setSiteUrl(url)
  }

  return { siteUrl, selectSite, ready }
}
