"use client"
import { formatDistanceToNow } from "date-fns"
import { Plus, MessageSquare, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useConversations, useDeleteConversation } from "@/hooks/use-hermes"

interface ConversationSidebarProps {
  workspaceId: string
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
}

export function ConversationSidebar({
  workspaceId,
  activeId,
  onSelect,
  onNew,
}: ConversationSidebarProps) {
  const { data: conversations = [], isLoading } = useConversations(workspaceId)
  const { mutate: deleteConversation } = useDeleteConversation(workspaceId)

  return (
    <div className="flex h-full w-60 shrink-0 flex-col border-r border-border/60 bg-muted/20">
      <div className="p-3">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-xl border border-border/60 bg-card px-3 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:border-indigo-500/40 hover:bg-indigo-500/8 hover:text-indigo-500"
        >
          <Plus size={15} />
          New chat
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        <p className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
          Conversations
        </p>
        {isLoading ? (
          <p className="px-2 py-2 text-xs text-muted-foreground">Loading…</p>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-2 text-xs text-muted-foreground">No conversations yet.</p>
        ) : (
          <div className="space-y-0.5">
            {conversations.map(c => (
              <div
                key={c.id}
                className={cn(
                  "group flex items-center gap-2 rounded-lg px-2 py-2 text-sm transition-colors cursor-pointer",
                  c.id === activeId
                    ? "bg-indigo-500/10 text-indigo-600"
                    : "text-foreground/80 hover:bg-muted/60"
                )}
                onClick={() => onSelect(c.id)}
              >
                <MessageSquare size={13} className="shrink-0 opacity-60" />
                <div className="min-w-0 flex-1">
                  <p className="truncate leading-tight">{c.title || "New chat"}</p>
                  {c.updated_at && (
                    <p className="text-[10px] text-muted-foreground/60">
                      {formatDistanceToNow(new Date(c.updated_at), { addSuffix: true })}
                    </p>
                  )}
                </div>
                <button
                  onClick={e => {
                    e.stopPropagation()
                    deleteConversation(c.id)
                  }}
                  className="shrink-0 text-muted-foreground/40 opacity-0 transition-all hover:text-destructive group-hover:opacity-100"
                  title="Delete conversation"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
