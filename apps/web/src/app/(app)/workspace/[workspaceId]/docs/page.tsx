"use client"
import { use, useState } from "react"
import { useDocuments, useCreateDocument } from "@/hooks/use-documents"
import { Button } from "@/components/ui/button"
import { Plus, FileText } from "lucide-react"
import Link from "next/link"
import { format } from "date-fns"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useRouter } from "next/navigation"

interface Doc {
  id: string
  title: string
  created_at: string
}

export default function DocsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = use(params)
  const { data: docs = [], isLoading } = useDocuments(workspaceId)
  const { mutateAsync: createDoc } = useCreateDocument(workspaceId)
  const [createOpen, setCreateOpen] = useState(false)
  const [title, setTitle] = useState("")
  const router = useRouter()

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    const doc = (await createDoc({ title })) as Doc
    setCreateOpen(false)
    setTitle("")
    router.push(`/workspace/${workspaceId}/docs/${doc.id}`)
  }

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Docs</h1>
        <Button onClick={() => setCreateOpen(true)} size="sm">
          <Plus size={16} className="mr-1.5" /> New doc
        </Button>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : !(docs as Doc[]).length ? (
        <div className="text-center py-16 text-muted-foreground">
          <FileText size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No documents yet. Create your first one.</p>
        </div>
      ) : (
        <div className="divide-y border rounded-xl overflow-hidden">
          {(docs as Doc[]).map((doc) => (
            <Link
              key={doc.id}
              href={`/workspace/${workspaceId}/docs/${doc.id}`}
              className="flex items-center gap-3 px-4 py-3 hover:bg-muted/30 transition-colors"
            >
              <FileText size={16} className="text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{doc.title}</p>
                <p className="text-xs text-muted-foreground">
                  {format(new Date(doc.created_at), "MMM d, yyyy")}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New document</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-1">
              <Label>Title</Label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Document title"
                required
                autoFocus
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="submit">Create</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
