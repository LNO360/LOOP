"use client"
import { useState } from "react"
import { useSeoContext } from "@/components/seo/seo-context"
import { IntegrationBanner } from "@/components/seo/integration-banner"
import {
  useSeoOverview, useGscAnalytics, gscDateRange, formatCtr, formatPosition,
} from "@/hooks/use-seo"
import { cn } from "@/lib/utils"

const PRESETS = [
  { label: "7d", days: 7 },
  { label: "28d", days: 28 },
  { label: "90d", days: 90 },
]

export default function SeoSearchPage() {
  const { workspaceId, siteUrl, siteReady } = useSeoContext()
  const [days, setDays] = useState(28)
  const [dimension, setDimension] = useState<"query" | "page">("query")

  const { data: overview } = useSeoOverview(workspaceId, siteUrl, days, siteReady)
  const range = gscDateRange(days)

  const { data: analytics, isLoading } = useGscAnalytics(
    workspaceId,
    siteUrl
      ? {
          site_url: siteUrl,
          start_date: range.start_date,
          end_date: range.end_date,
          dimensions: dimension,
          row_limit: 50,
        }
      : null
  )

  const rows = analytics?.rows ?? []

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      <IntegrationBanner workspaceId={workspaceId} overview={overview} siteUrl={siteUrl} siteReady={siteReady} />

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-lg border border-border/60 overflow-hidden">
          {PRESETS.map((p) => (
            <button
              key={p.days}
              onClick={() => setDays(p.days)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium transition-colors",
                days === p.days
                  ? "bg-foreground text-background"
                  : "bg-background text-muted-foreground hover:text-foreground"
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="flex rounded-lg border border-border/60 overflow-hidden">
          {(["query", "page"] as const).map((d) => (
            <button
              key={d}
              onClick={() => setDimension(d)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                dimension === d
                  ? "bg-foreground text-background"
                  : "bg-background text-muted-foreground hover:text-foreground"
              )}
            >
              {d === "query" ? "Queries" : "Pages"}
            </button>
          ))}
        </div>
        {analytics && (
          <span className="text-xs text-muted-foreground">
            {analytics.start_date} → {analytics.end_date}
          </span>
        )}
      </div>

      {!siteUrl ? (
        <div className="rounded-xl border border-dashed border-border/60 p-12 text-center text-sm text-muted-foreground">
          Select a Search Console property in the header to view search performance.
        </div>
      ) : (
        <div className="rounded-xl border border-border/60 bg-white dark:bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-border/60 bg-slate-50/60 dark:bg-muted/30">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">
                  {dimension === "query" ? "Query" : "Page"}
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Clicks</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Impressions</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">CTR</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Position</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">Loading…</td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No data for this period</td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.keys.join("-")} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 truncate max-w-md" title={row.keys[0]}>{row.keys[0]}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{row.clicks}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{row.impressions}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{formatCtr(row.ctr)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{formatPosition(row.position)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
