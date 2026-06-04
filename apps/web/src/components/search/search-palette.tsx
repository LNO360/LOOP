"use client"
import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Search, CheckSquare, FileText, MessageSquare, X } from "lucide-react"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"

interface SearchResult {
  tasks: Array<{ id: string; title: string; status: string; priority: string }>
  docs: Array<{ id: string; title: string }>
  messages: Array<{ id: string; content: string; channel_id: string }>
}

interface SearchPaletteProps {
  workspaceId: string
  onClose: () => void
}

const priorityDot: Record<string, string> = {
  low: "bg-slate-400",
  medium: "bg-amber-400",
  high: "bg-orange-500",
  urgent: "bg-red-500",
}

export function SearchPalette({ workspaceId, onClose }: SearchPaletteProps) {
  const [query, setQuery] = useState("")
  const router = useRouter()

  const { data: results } = useQuery({
    queryKey: ["search", workspaceId, query],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/search?q=${encodeURIComponent(query)}`)
        .then((r) => r.data as SearchResult),
    enabled: query.length >= 2,
    staleTime: 0,
  })

  const hasResults =
    results &&
    results.tasks.length + results.docs.length + results.messages.length > 0

  function handleNavigate(href: string) {
    router.push(href)
    onClose()
  }

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-start justify-center pt-[15vh] z-50 px-4"
      onClick={onClose}
    >
      <div
        className="bg-background rounded-2xl shadow-2xl border w-full max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b">
          <Search size={16} className="text-muted-foreground shrink-0" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search tasks, docs, messages…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="text-muted-foreground hover:text-foreground"
            >
              <X size={14} />
            </button>
          )}
          <kbd className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded border">
            esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto py-2">
          {query.length < 2 ? (
            <p className="text-xs text-muted-foreground text-center py-8">
              Type to search…
            </p>
          ) : !hasResults ? (
            <p className="text-xs text-muted-foreground text-center py-8">
              No results for &ldquo;{query}&rdquo;
            </p>
          ) : (
            <>
              {results.tasks.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-4 py-1.5">
                    Tasks
                  </p>
                  {results.tasks.map((t) => (
                    <button
                      key={t.id}
                      onClick={() =>
                        handleNavigate(`/workspace/${workspaceId}/tasks`)
                      }
                      className="flex items-center gap-2.5 w-full px-4 py-2 hover:bg-muted/50 transition-colors text-left"
                    >
                      <span
                        className={cn(
                          "h-2 w-2 rounded-full shrink-0",
                          priorityDot[t.priority] ?? "bg-slate-400"
                        )}
                      />
                      <CheckSquare
                        size={13}
                        className="text-muted-foreground shrink-0"
                      />
                      <span className="text-sm truncate">{t.title}</span>
                      <span className="ml-auto text-xs text-muted-foreground capitalize shrink-0">
                        {t.status.replace("_", " ")}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {results.docs.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-4 py-1.5">
                    Docs
                  </p>
                  {results.docs.map((d) => (
                    <button
                      key={d.id}
                      onClick={() =>
                        handleNavigate(
                          `/workspace/${workspaceId}/docs/${d.id}`
                        )
                      }
                      className="flex items-center gap-2.5 w-full px-4 py-2 hover:bg-muted/50 transition-colors text-left"
                    >
                      <FileText
                        size={13}
                        className="text-muted-foreground shrink-0"
                      />
                      <span className="text-sm truncate">{d.title}</span>
                    </button>
                  ))}
                </div>
              )}

              {results.messages.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-4 py-1.5">
                    Messages
                  </p>
                  {results.messages.map((m) => (
                    <button
                      key={m.id}
                      onClick={() =>
                        handleNavigate(
                          `/workspace/${workspaceId}/channel/${m.channel_id}`
                        )
                      }
                      className="flex items-center gap-2.5 w-full px-4 py-2 hover:bg-muted/50 transition-colors text-left"
                    >
                      <MessageSquare
                        size={13}
                        className="text-muted-foreground shrink-0"
                      />
                      <span className="text-sm truncate text-muted-foreground">
                        {m.content}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
