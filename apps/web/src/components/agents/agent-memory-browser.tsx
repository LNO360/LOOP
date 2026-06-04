"use client"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Database } from "lucide-react"

interface MemoryEntry {
  key: string
  content: string
  importance: number
  source: string
}

interface MemoryResponse {
  memories: MemoryEntry[]
}

function importanceBg(n: number): string {
  if (n >= 5) return "bg-red-500"
  if (n >= 4) return "bg-orange-500"
  if (n >= 3) return "bg-yellow-500"
  return "bg-muted-foreground"
}

function ImportanceDots({ n }: { n: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "w-1.5 h-1.5 rounded-full",
            i < n ? importanceBg(n) : "bg-muted"
          )}
        />
      ))}
    </div>
  )
}

export function AgentMemoryBrowser({ workspaceId }: { workspaceId: string }) {
  const { data, isLoading } = useQuery<MemoryResponse>({
    queryKey: ["agent-memory", workspaceId],
    queryFn: () =>
      api
        .get(`/workspaces/${workspaceId}/agent-memory`)
        .then((r) => r.data),
    refetchInterval: 60_000,
    enabled: !!workspaceId,
  })

  const memories = data?.memories ?? []

  // Group by namespace (first segment of dot-notation key)
  const grouped = memories.reduce<Record<string, MemoryEntry[]>>((acc, m) => {
    const ns = m.key.split(".")[0]
    acc[ns] = acc[ns] ?? []
    acc[ns].push(m)
    return acc
  }, {})

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    )
  }

  if (memories.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
        <Database size={24} className="mb-2 opacity-40" />
        <p className="text-sm">No memories yet</p>
        <p className="text-xs mt-1">
          Hermes will store observations here as it runs
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([namespace, entries]) => (
        <div key={namespace} className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground px-1">
            {namespace}
          </h3>
          <div className="space-y-1">
            {entries.map((entry) => (
              <div
                key={entry.key}
                className="rounded-lg border px-3 py-2.5 space-y-1 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <code className="text-xs font-mono text-foreground">
                    {entry.key}
                  </code>
                  <ImportanceDots n={entry.importance} />
                </div>
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {entry.content}
                </p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
