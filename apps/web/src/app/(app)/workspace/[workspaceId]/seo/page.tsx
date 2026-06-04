"use client"
import Link from "next/link"
import {
  MousePointerClick, Eye, TrendingUp, FileWarning, BarChart3, ArrowRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useSeoContext } from "@/components/seo/seo-context"
import { IntegrationBanner } from "@/components/seo/integration-banner"
import { SeoScoreBadge } from "@/components/seo/seo-score-badge"
import {
  useSeoOverview, formatCtr, formatPosition,
} from "@/hooks/use-seo"

interface OverviewCardProps {
  label: string
  value: string
  subtext?: string
  icon: React.ElementType
  positive?: boolean
  negative?: boolean
}

function OverviewCard({ label, value, subtext, icon: Icon, positive, negative }: OverviewCardProps) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card p-5 shadow-sm flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
        <div className={cn(
          "flex h-8 w-8 items-center justify-center rounded-xl",
          positive ? "bg-emerald-500/10 text-emerald-500" :
          negative ? "bg-rose-500/10 text-rose-500" :
          "bg-muted text-muted-foreground"
        )}>
          <Icon size={16} />
        </div>
      </div>
      <p className={cn(
        "text-2xl font-bold tracking-tight",
        positive ? "text-emerald-600" :
        negative ? "text-rose-600" :
        "text-foreground"
      )}>{value}</p>
      {subtext && <p className="text-xs text-muted-foreground">{subtext}</p>}
    </div>
  )
}

function MiniTable({
  title,
  rows,
  keyLabel,
}: {
  title: string
  rows: { keys: string[]; clicks: number; impressions: number; ctr: number; position: number }[]
  keyLabel: string
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-border/60 bg-card p-4">
        <p className="text-sm font-medium mb-2">{title}</p>
        <p className="text-xs text-muted-foreground">No data for this period</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border/60">
        <p className="text-sm font-medium">{title}</p>
      </div>
      <table className="w-full text-sm">
        <thead className="border-b border-border/60 bg-slate-50/60 dark:bg-muted/30">
          <tr>
            <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">{keyLabel}</th>
            <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Clicks</th>
            <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Impr.</th>
            <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Pos.</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/40">
          {rows.map((row) => (
            <tr key={row.keys.join("-")}>
              <td className="px-4 py-2 truncate max-w-[200px]" title={row.keys[0]}>{row.keys[0]}</td>
              <td className="px-4 py-2 text-right tabular-nums">{row.clicks}</td>
              <td className="px-4 py-2 text-right tabular-nums">{row.impressions}</td>
              <td className="px-4 py-2 text-right tabular-nums">{formatPosition(row.position)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function SeoOverviewPage() {
  const { workspaceId, siteUrl, siteReady } = useSeoContext()
  const { data: overview, isLoading } = useSeoOverview(workspaceId, siteUrl, 28, siteReady)

  const gsc = overview?.gsc
  const blog = overview?.blog

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      <IntegrationBanner workspaceId={workspaceId} overview={overview} siteUrl={siteUrl} siteReady={siteReady} />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <OverviewCard
          label="Clicks (28d)"
          value={isLoading ? "…" : gsc?.available ? String(gsc.clicks ?? 0) : "—"}
          subtext={gsc?.available ? `${gsc.start_date} → ${gsc.end_date}` : "Connect Google + select property"}
          icon={MousePointerClick}
        />
        <OverviewCard
          label="Impressions"
          value={isLoading ? "…" : gsc?.available ? String(gsc.impressions ?? 0) : "—"}
          icon={Eye}
        />
        <OverviewCard
          label="Avg Position"
          value={isLoading ? "…" : gsc?.available ? formatPosition(gsc.avg_position ?? 0) : "—"}
          icon={TrendingUp}
          positive={(gsc?.avg_position ?? 99) < 10}
        />
        <OverviewCard
          label="Avg SEO Score"
          value={isLoading ? "…" : blog?.available ? String(blog.avg_score ?? 0) : "—"}
          subtext={blog?.available ? `${blog.total_posts} posts` : "Blog not configured"}
          icon={BarChart3}
          positive={(blog?.avg_score ?? 0) >= 80}
          negative={(blog?.avg_score ?? 100) < 60}
        />
        <OverviewCard
          label="Posts Needing Fixes"
          value={isLoading ? "…" : blog?.available ? String(blog.posts_needing_fixes ?? 0) : "—"}
          subtext="Score below 70"
          icon={FileWarning}
          negative={(blog?.posts_needing_fixes ?? 0) > 0}
        />
      </div>

      {gsc?.available && (
        <div className="grid md:grid-cols-2 gap-4">
          <MiniTable title="Top Queries" rows={gsc.top_queries ?? []} keyLabel="Query" />
          <MiniTable title="Top Pages" rows={gsc.top_pages ?? []} keyLabel="Page" />
        </div>
      )}

      {blog?.available && (
        <div className="rounded-2xl border border-border/60 bg-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-medium">Content Health</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {blog.published_count} published · {blog.draft_count} drafts
                {gsc?.available && ` · CTR ${formatCtr(gsc.ctr ?? 0)}`}
              </p>
            </div>
            {blog.avg_score != null && <SeoScoreBadge score={blog.avg_score} />}
          </div>
          <div className="flex gap-3">
            <Link
              href={`/workspace/${workspaceId}/seo/content`}
              className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
            >
              View all posts <ArrowRight size={14} />
            </Link>
            <Link
              href={`/workspace/${workspaceId}/seo/assistant`}
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Run audit in Assistant <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      )}

      {gsc?.available && (gsc.sitemap_errors ?? 0) + (gsc.sitemap_warnings ?? 0) > 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm">
          Sitemap issues: {gsc.sitemap_errors} errors, {gsc.sitemap_warnings} warnings.{" "}
          <Link href={`/workspace/${workspaceId}/seo/technical`} className="text-primary hover:underline">
            View technical tab
          </Link>
        </div>
      )}
    </div>
  )
}
