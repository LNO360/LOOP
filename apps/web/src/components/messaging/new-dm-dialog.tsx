"use client"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useCreateDM } from "@/hooks/use-dms"
import { useRouter } from "next/navigation"
import { Search } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

interface NewDMDialogProps {
  workspaceId: string
  currentUserId: string
  onClose: () => void
}

export function NewDMDialog({ workspaceId, currentUserId, onClose }: NewDMDialogProps) {
  const [query, setQuery] = useState("")
  const router = useRouter()
  const { data: members = [] } = useQuery({
    queryKey: ["members", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/members`).then((r) => r.data),
  })
  const { mutateAsync: createDM } = useCreateDM(workspaceId)

  const filtered = (members as Array<{ id: string; name: string }>)
    .filter((m) => m.id !== currentUserId)
    .filter((m) => m.name.toLowerCase().includes(query.toLowerCase()))

  async function handleSelect(userId: string) {
    const dm = await createDM(userId)
    router.push(`/workspace/${workspaceId}/dm/${dm.id}`)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-background rounded-2xl shadow-2xl w-80 overflow-hidden border"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-3 border-b">
          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-muted">
            <Search size={13} className="text-muted-foreground shrink-0" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search people…"
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
        </div>
        <div className="py-1 max-h-60 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-6">No members found</p>
          ) : (
            filtered.map((m) => (
              <button
                key={m.id}
                onClick={() => handleSelect(m.id)}
                className="flex items-center gap-2.5 w-full px-3 py-2 hover:bg-muted/50 transition-colors text-left"
              >
                <Avatar className="h-7 w-7 shrink-0">
                  <AvatarFallback className="text-xs bg-accent text-white">
                    {m.name[0].toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <span className="text-sm">{m.name}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
