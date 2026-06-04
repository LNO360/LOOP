"use client"
import { useState } from "react"
import { ExternalLink, Loader2, Search } from "lucide-react"
import { useSeoContext } from "@/components/seo/seo-context"
import { IntegrationBanner } from "@/components/seo/integration-banner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useSeoOverview, useGscSitemaps, useUrlInspect } from "@/hooks/use-seo"
import { cn } from "@/lib/utils"

export default function SeoTechnicalPage() {
  const { workspaceId, siteUrl, siteReady } = useSeoContext()
  const { data: overview } = useSeoOverview(workspaceId, siteUrl, 28, siteReady)
  const { data: sitemapsData, isLoading: sitemapsLoading } = useGscSitemaps(workspaceId, siteUrl)
  const inspect = useUrlInspect(workspaceId)

  const [inspectUrl, setInspectUrl] = useState("")
  const sitemaps = sitemapsData?.sitemaps ?? []
  const result = inspect.data

  const handleInspect = () => {
    if (!siteUrl || !inspectUrl.trim()) return
    inspect.mutate({ site_url: siteUrl, inspection_url: inspectUrl.trim() })
  }

  return (
    <div className="p-6 space-y-8 max-w-6xl">
      <IntegrationBanner workspaceId={workspaceId} overview={overview} siteUrl={siteUrl} siteReady={siteReady} />

      <section>
        <h2 className="text-sm font-semibold mb-3">Sitemaps</h2>
        {!siteUrl ? (
          <p className="text-sm text-muted-foreground">Select a Search Console property to view sitemaps.</p>
        ) : (
          <div className="rounded-xl border border-border/60 bg-white dark:bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-border/60 bg-slate-50/60 dark:bg-muted/30">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Path</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Last submitted</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Errors</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Warnings</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Pending</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {sitemapsLoading ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">Loading…</td>
                  </tr>
                ) : sitemaps.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No sitemaps found</td>
                  </tr>
                ) : (
                  sitemaps.map((sm) => (
                    <tr key={sm.path}>
                      <td className="px-4 py-2.5 truncate max-w-md" title={sm.path}>{sm.path}</td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground">
                        {sm.lastSubmitted ? new Date(sm.lastSubmitted).toLocaleDateString() : "—"}
                      </td>
                      <td className={cn(
                        "px-4 py-2.5 text-right tabular-nums",
                        (sm.errors ?? 0) > 0 && "text-rose-600 font-medium"
                      )}>
                        {sm.errors ?? 0}
                      </td>
                      <td className={cn(
                        "px-4 py-2.5 text-right tabular-nums",
                        (sm.warnings ?? 0) > 0 && "text-amber-600"
                      )}>
                        {sm.warnings ?? 0}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {sm.isPending ? "Yes" : "No"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold mb-3">URL Inspection</h2>
        <div className="rounded-xl border border-border/60 bg-card p-5 space-y-4 max-w-xl">
          <div>
            <Label htmlFor="url">URL to inspect</Label>
            <div className="flex gap-2 mt-1">
              <Input
                id="url"
                placeholder="https://your-domain.com/blog/my-post"
                value={inspectUrl}
                onChange={(e) => setInspectUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleInspect()}
              />
              <Button onClick={handleInspect} disabled={!siteUrl || inspect.isPending}>
                {inspect.isPending ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              </Button>
            </div>
          </div>

          {inspect.isError && (
            <p className="text-sm text-rose-600">{inspect.error.message}</p>
          )}

          {result && (
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {[
                ["Verdict", result.verdict],
                ["Coverage", result.coverageState],
                ["Indexing", result.indexingState],
                ["Last crawl", result.lastCrawlTime ? new Date(result.lastCrawlTime).toLocaleString() : "—"],
                ["Mobile", result.mobileUsability],
                ["Rich results", result.richResults],
                ["Robots.txt", result.robotsTxtState],
                ["Google canonical", result.googleCanonical],
              ].map(([label, value]) => (
                <div key={label as string}>
                  <dt className="text-xs text-muted-foreground">{label}</dt>
                  <dd className="font-medium truncate" title={String(value ?? "—")}>{value ?? "—"}</dd>
                </div>
              ))}
            </dl>
          )}

          {result?.inspectionResultLink && (
            <a
              href={result.inspectionResultLink}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
            >
              Open in Search Console <ExternalLink size={14} />
            </a>
          )}
        </div>
      </section>
    </div>
  )
}
