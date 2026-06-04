import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

const base = (wsId: string) => `/workspaces/${wsId}/seo`

// ── Types ─────────────────────────────────────────────────────────────────────

export interface GscSite {
  siteUrl: string
  permissionLevel: string
}

export interface GscRow {
  keys: string[]
  clicks: number
  impressions: number
  ctr: number
  position: number
}

export interface GscAnalytics {
  site_url: string
  start_date: string
  end_date: string
  dimensions: string[]
  rows: GscRow[]
}

export interface GscSitemap {
  path: string
  lastSubmitted?: string
  isPending?: boolean
  errors?: number
  warnings?: number
  contents?: unknown[]
}

export interface UrlInspection {
  inspection_url: string
  verdict?: string
  coverageState?: string
  lastCrawlTime?: string
  googleCanonical?: string
  userCanonical?: string
  robotsTxtState?: string
  indexingState?: string
  mobileUsability?: string
  richResults?: string
  inspectionResultLink?: string
}

export interface SeoAudit {
  post_id: string
  title_length: number
  has_meta_description: boolean
  meta_description_length: number
  has_excerpt: boolean
  has_tags: boolean
  tag_count: number
  has_cover_image: boolean
  has_slug: boolean
  estimated_word_count: number
  issues: string[]
  score: number
}

export interface BlogPostSummary {
  id: string
  title: string
  slug: string
  status: string
  category?: string
  tags?: string[]
  published_at?: string
  updated_at?: string
  score?: number
  issues?: string[]
  issue_count?: number
}

export interface BlogPost extends BlogPostSummary {
  content?: unknown
  meta_description?: string
  excerpt?: string
  cover_image_url?: string
}

export interface SeoOverview {
  google_connected: boolean
  blog_configured: boolean
  gsc: {
    available: boolean
    reason?: string
    site_url?: string
    start_date?: string
    end_date?: string
    clicks?: number
    impressions?: number
    ctr?: number
    avg_position?: number
    top_queries?: GscRow[]
    top_pages?: GscRow[]
    sitemap_errors?: number
    sitemap_warnings?: number
  }
  blog: {
    available: boolean
    reason?: string
    total_posts?: number
    draft_count?: number
    published_count?: number
    avg_score?: number
    posts_needing_fixes?: number
  }
}

// ── GSC site persistence ──────────────────────────────────────────────────────

export function gscSiteStorageKey(workspaceId: string) {
  return `seo-gsc-site-${workspaceId}`
}

export function getStoredGscSite(workspaceId: string): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem(gscSiteStorageKey(workspaceId))
}

export function setStoredGscSite(workspaceId: string, siteUrl: string) {
  localStorage.setItem(gscSiteStorageKey(workspaceId), siteUrl)
}

// ── Date helpers ──────────────────────────────────────────────────────────────

export function gscDateRange(days: number): { start_date: string; end_date: string } {
  const end = new Date()
  end.setDate(end.getDate() - 3) // GSC data lags ~2-3 days
  const start = new Date(end)
  start.setDate(start.getDate() - (days - 1))
  return {
    start_date: start.toISOString().slice(0, 10),
    end_date: end.toISOString().slice(0, 10),
  }
}

export function formatCtr(ctr: number): string {
  return `${(ctr * 100).toFixed(1)}%`
}

export function formatPosition(pos: number): string {
  return pos.toFixed(1)
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useSeoOverview(
  workspaceId: string,
  siteUrl: string | null,
  days = 28,
  siteReady = true,
) {
  return useQuery<SeoOverview>({
    queryKey: ["seo", workspaceId, "overview", siteUrl, days],
    queryFn: () =>
      api
        .get(`${base(workspaceId)}/overview`, {
          params: { site_url: siteUrl ?? undefined, days },
        })
        .then((r) => r.data),
    enabled: !!workspaceId && siteReady,
  })
}

export function useGscSites(workspaceId: string) {
  return useQuery<{ sites: GscSite[] }>({
    queryKey: ["seo", workspaceId, "gsc-sites"],
    queryFn: () => api.get(`${base(workspaceId)}/gsc/sites`).then((r) => r.data),
    enabled: !!workspaceId,
  })
}

export function useGscAnalytics(
  workspaceId: string,
  params: {
    site_url: string
    start_date: string
    end_date: string
    dimensions?: string
    row_limit?: number
  } | null
) {
  return useQuery<GscAnalytics>({
    queryKey: ["seo", workspaceId, "gsc-analytics", params],
    queryFn: () =>
      api.get(`${base(workspaceId)}/gsc/analytics`, { params: params! }).then((r) => r.data),
    enabled: !!workspaceId && !!params?.site_url,
  })
}

export function useGscSitemaps(workspaceId: string, siteUrl: string | null) {
  return useQuery<{ sitemaps: GscSitemap[] }>({
    queryKey: ["seo", workspaceId, "gsc-sitemaps", siteUrl],
    queryFn: () =>
      api
        .get(`${base(workspaceId)}/gsc/sitemaps`, { params: { site_url: siteUrl } })
        .then((r) => r.data),
    enabled: !!workspaceId && !!siteUrl,
  })
}

export function useUrlInspect(workspaceId: string) {
  return useMutation<UrlInspection, Error, { site_url: string; inspection_url: string }>({
    mutationFn: (body) =>
      api.post(`${base(workspaceId)}/gsc/inspect`, body).then((r) => r.data),
  })
}

export function useBlogPosts(
  workspaceId: string,
  params?: { status?: string; include_audit?: boolean }
) {
  return useQuery<{ posts: BlogPostSummary[] }>({
    queryKey: ["seo", workspaceId, "blog-posts", params],
    queryFn: () =>
      api
        .get(`${base(workspaceId)}/blog/posts`, {
          params: {
            status: params?.status || "all",
            include_audit: params?.include_audit ?? false,
            limit: 50,
          },
        })
        .then((r) => r.data),
    enabled: !!workspaceId,
  })
}

export function useBlogPost(workspaceId: string, postId: string | null) {
  return useQuery<BlogPost>({
    queryKey: ["seo", workspaceId, "blog-post", postId],
    queryFn: () => api.get(`${base(workspaceId)}/blog/posts/${postId}`).then((r) => r.data),
    enabled: !!workspaceId && !!postId,
  })
}

export function useBlogAudit(workspaceId: string, postId: string | null) {
  return useQuery<SeoAudit>({
    queryKey: ["seo", workspaceId, "blog-audit", postId],
    queryFn: () =>
      api.get(`${base(workspaceId)}/blog/posts/${postId}/audit`).then((r) => r.data),
    enabled: !!workspaceId && !!postId,
  })
}

export function useUpdateBlogPost(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      postId,
      ...body
    }: {
      postId: string
      title?: string
      slug?: string
      excerpt?: string
      meta_description?: string
      tags?: string[]
      cover_image_url?: string
    }) => api.patch(`${base(workspaceId)}/blog/posts/${postId}`, body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["seo", workspaceId] })
    },
  })
}

export function useProposeBlogPublish(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (postId: string) =>
      api.post(`${base(workspaceId)}/blog/posts/${postId}/publish`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["seo", workspaceId] })
      qc.invalidateQueries({ queryKey: ["proposed-actions", workspaceId] })
    },
  })
}
