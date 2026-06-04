"use client"
import { useState, useEffect } from "react"
import Link from "next/link"
import { Bot, Loader2 } from "lucide-react"
import { useSeoContext } from "@/components/seo/seo-context"
import { IntegrationBanner } from "@/components/seo/integration-banner"
import { SeoScoreBadge } from "@/components/seo/seo-score-badge"
import { AuditIssuesList } from "@/components/seo/audit-issues-list"
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  useSeoOverview, useBlogPosts, useBlogPost, useBlogAudit,
  useUpdateBlogPost, useProposeBlogPublish,
} from "@/hooks/use-seo"
import { cn } from "@/lib/utils"

export default function SeoContentPage() {
  const { workspaceId, siteUrl, siteReady } = useSeoContext()
  const [statusFilter, setStatusFilter] = useState("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: overview } = useSeoOverview(workspaceId, siteUrl, 28, siteReady)
  const { data, isLoading } = useBlogPosts(workspaceId, {
    status: statusFilter,
    include_audit: true,
  })
  const posts = data?.posts ?? []

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      <IntegrationBanner workspaceId={workspaceId} overview={overview} siteUrl={siteUrl} siteReady={siteReady} />

      <div className="flex items-center gap-2">
        {(["all", "draft", "published"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium capitalize border transition-colors",
              statusFilter === s
                ? "border-foreground bg-foreground text-background"
                : "border-border/60 text-muted-foreground hover:text-foreground"
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {!overview?.blog_configured ? (
        <div className="rounded-xl border border-dashed border-border/60 p-12 text-center text-sm text-muted-foreground">
          Blog CMS not configured on the API server.
        </div>
      ) : (
        <div className="rounded-xl border border-border/60 bg-white dark:bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-border/60 bg-slate-50/60 dark:bg-muted/30">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Title</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">SEO Score</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Issues</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">Loading…</td>
                </tr>
              ) : posts.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No posts found</td>
                </tr>
              ) : (
                posts.map((post) => (
                  <tr
                    key={post.id}
                    className="hover:bg-muted/30 cursor-pointer"
                    onClick={() => setSelectedId(post.id)}
                  >
                    <td className="px-4 py-2.5">
                      <p className="font-medium truncate max-w-xs">{post.title}</p>
                      <p className="text-xs text-muted-foreground truncate max-w-xs">{post.slug}</p>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={cn(
                        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                        post.status === "published"
                          ? "bg-emerald-500/10 text-emerald-700"
                          : "bg-muted text-muted-foreground"
                      )}>
                        {post.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {post.score != null && <SeoScoreBadge score={post.score} />}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">
                      {post.issue_count ?? 0}
                    </td>
                    <td className="px-4 py-2.5 text-right text-xs text-muted-foreground">
                      {post.updated_at ? new Date(post.updated_at).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <PostDetailSheet
        workspaceId={workspaceId}
        postId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  )
}

function PostDetailSheet({
  workspaceId,
  postId,
  onClose,
}: {
  workspaceId: string
  postId: string | null
  onClose: () => void
}) {
  const { data: post } = useBlogPost(workspaceId, postId)
  const { data: audit } = useBlogAudit(workspaceId, postId)
  const updatePost = useUpdateBlogPost(workspaceId)
  const proposePublish = useProposeBlogPublish(workspaceId)

  const [title, setTitle] = useState("")
  const [metaDescription, setMetaDescription] = useState("")
  const [excerpt, setExcerpt] = useState("")
  const [tags, setTags] = useState("")

  useEffect(() => {
    if (post) {
      setTitle(post.title ?? "")
      setMetaDescription(post.meta_description ?? "")
      setExcerpt(post.excerpt ?? "")
      setTags((post.tags ?? []).join(", "))
    }
  }, [post])

  if (!postId) return null

  const handleSave = () => {
    updatePost.mutate({
      postId,
      title: title || undefined,
      meta_description: metaDescription || undefined,
      excerpt: excerpt || undefined,
      tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : undefined,
    })
  }

  const askAiHref = `/workspace/${workspaceId}/seo/assistant?context=${encodeURIComponent(
    `Post "${post?.title}" (score ${audit?.score ?? "?"}): issues: ${(audit?.issues ?? []).join(", ")}`
  )}`

  return (
    <Sheet open={!!postId} onOpenChange={(open) => { if (!open) onClose() }}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="truncate">{post?.title ?? "Post details"}</SheetTitle>
        </SheetHeader>

        {audit && (
          <div className="mt-4">
            <SeoScoreBadge score={audit.score} />
            <div className="mt-3">
              <AuditIssuesList issues={audit.issues} />
            </div>
          </div>
        )}

        <div className="mt-6 space-y-4">
          <div>
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1" />
            {audit && (
              <p className="text-xs text-muted-foreground mt-1">{audit.title_length} chars (ideal: 10–60)</p>
            )}
          </div>
          <div>
            <Label htmlFor="meta">Meta description</Label>
            <Textarea
              id="meta"
              value={metaDescription}
              onChange={(e) => setMetaDescription(e.target.value)}
              className="mt-1"
              rows={3}
            />
            {audit && (
              <p className="text-xs text-muted-foreground mt-1">
                {audit.meta_description_length} chars (ideal: 50–160)
              </p>
            )}
          </div>
          <div>
            <Label htmlFor="excerpt">Excerpt</Label>
            <Textarea
              id="excerpt"
              value={excerpt}
              onChange={(e) => setExcerpt(e.target.value)}
              className="mt-1"
              rows={2}
            />
          </div>
          <div>
            <Label htmlFor="tags">Tags (comma-separated)</Label>
            <Input id="tags" value={tags} onChange={(e) => setTags(e.target.value)} className="mt-1" />
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          <Button onClick={handleSave} disabled={updatePost.isPending}>
            {updatePost.isPending && <Loader2 size={14} className="mr-1 animate-spin" />}
            Save
          </Button>
          {post?.status === "draft" && (
            <Button
              variant="outline"
              onClick={() => proposePublish.mutate(postId)}
              disabled={proposePublish.isPending}
            >
              Propose publish
            </Button>
          )}
          <Link
            href={askAiHref}
            className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Bot size={14} />
            Ask AI
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  )
}
