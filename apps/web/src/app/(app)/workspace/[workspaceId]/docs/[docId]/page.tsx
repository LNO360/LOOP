"use client"
import { use, useState, useRef } from "react"
import { useDocument, useUpdateDocument } from "@/hooks/use-documents"
import { DocEditor } from "@/components/docs/doc-editor"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useDebouncedCallback } from "use-debounce"
import { useRunDocsAgent } from "@/hooks/use-agents"
import { Sparkles, Wand2, FileText, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface DocData {
  id: string
  title: string
  content: unknown
}

export default function DocDetailPage({
  params,
}: {
  params: Promise<{ workspaceId: string; docId: string }>
}) {
  const { workspaceId, docId } = use(params)
  const { data: doc, isLoading } = useDocument(workspaceId, docId) as {
    data: DocData | undefined
    isLoading: boolean
  }
  const { mutate: updateDoc } = useUpdateDocument(workspaceId)
  const { mutateAsync: runDocsAgent, isPending: aiPending } = useRunDocsAgent(workspaceId)
  const [aiResult, setAiResult] = useState<string | null>(null)
  const editorContentRef = useRef<unknown>(null)

  const save = useDebouncedCallback(
    (data: { title?: string; content?: unknown }) => {
      if (!doc) return
      updateDoc({ docId, data: { title: data.title ?? doc.title, content: data.content ?? doc.content } })
    },
    1000
  )

  function handleEditorChange(json: unknown) {
    editorContentRef.current = json
    save({ content: json })
  }

  function getTextContent(content: unknown): string {
    if (!content) return ""
    try {
      const json = typeof content === "string" ? JSON.parse(content) : content
      const extract = (node: unknown): string => {
        if (!node || typeof node !== "object") return ""
        const n = node as Record<string, unknown>
        if (n.type === "text") return String(n.text ?? "")
        if (Array.isArray(n.content)) return (n.content as unknown[]).map(extract).join(" ")
        return ""
      }
      return extract(json)
    } catch { return "" }
  }

  async function handleAI(action: "draft" | "improve") {
    const currentContent = editorContentRef.current ?? doc?.content
    const textContent = getTextContent(currentContent)
    if (!textContent.trim()) return

    try {
      const res = await runDocsAgent({ action, content: textContent })
      setAiResult(res.content)
    } catch {
      setAiResult("AI is unavailable. Check your API key.")
    }
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    )
  }

  if (!doc) return <div className="p-6 text-muted-foreground">Document not found.</div>

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <Input
        defaultValue={doc.title}
        onChange={(e) => save({ title: e.target.value })}
        className="text-2xl font-semibold border-none shadow-none px-0 mb-4 focus-visible:ring-0 text-foreground"
        placeholder="Untitled"
      />

      {/* AI Toolbar */}
      <div className="flex items-center gap-2 mb-4 pb-3 border-b">
        <Sparkles size={13} className="text-accent" />
        <span className="text-xs font-medium text-muted-foreground mr-1">AI</span>
        {[
          { action: "draft" as const, label: "Draft from outline", icon: FileText },
          { action: "improve" as const, label: "Improve writing", icon: Wand2 },
        ].map(({ action, label, icon: Icon }) => (
          <button
            key={action}
            onClick={() => handleAI(action)}
            disabled={aiPending}
            className={cn(
              "flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg border hover:bg-muted/50 transition-colors disabled:opacity-50 text-muted-foreground hover:text-foreground"
            )}
          >
            {aiPending ? <Loader2 size={11} className="animate-spin" /> : <Icon size={11} />}
            {label}
          </button>
        ))}
      </div>

      {/* AI Result overlay */}
      {aiResult && (
        <div className="mb-4 rounded-xl border bg-accent/5 border-accent/20 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-accent flex items-center gap-1.5">
              <Sparkles size={11} /> AI suggestion
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  save({ content: aiResult })
                  setAiResult(null)
                }}
                className="text-xs px-2.5 py-1 rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors"
              >
                Accept
              </button>
              <button
                onClick={() => setAiResult(null)}
                className="text-xs px-2 py-1 rounded-lg hover:bg-muted transition-colors text-muted-foreground"
              >
                Dismiss
              </button>
            </div>
          </div>
          <pre className="text-xs leading-relaxed whitespace-pre-wrap font-sans max-h-48 overflow-y-auto text-foreground/80">
            {aiResult}
          </pre>
        </div>
      )}

      <DocEditor
        content={doc.content}
        onChange={handleEditorChange}
      />
    </div>
  )
}
