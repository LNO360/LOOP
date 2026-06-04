"use client"
import { X } from "lucide-react"
import { MessageItem } from "./message-item"
import { MessageComposer } from "./message-composer"
import { useThread, useReplyToThread } from "@/hooks/use-thread"
import { Skeleton } from "@/components/ui/skeleton"
import type { Message } from "@/hooks/use-messages"

interface ThreadPanelProps {
  parentMessage: Message | null
  workspaceId: string
  channelId: string
  members: Record<string, string>
  memberList: Array<{ id: string; name: string }>
  currentUserId: string
  onClose: () => void
}

export function ThreadPanel({
  parentMessage,
  workspaceId,
  channelId,
  members,
  memberList,
  currentUserId,
  onClose,
}: ThreadPanelProps) {
  const { data: replies = [], isLoading } = useThread(workspaceId, channelId, parentMessage?.id ?? null)
  const { mutate: reply } = useReplyToThread(workspaceId, channelId)

  if (!parentMessage) return null

  return (
    <div className="w-80 border-l flex flex-col shrink-0 bg-background">
      {/* Header */}
      <div className="h-14 border-b flex items-center justify-between px-4 shrink-0">
        <div>
          <span className="font-medium text-sm">Thread</span>
          {replies.length > 0 && (
            <span className="ml-2 text-xs text-muted-foreground">{replies.length} repl{replies.length === 1 ? "y" : "ies"}</span>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* Parent message */}
      <div className="border-b bg-muted/20 py-1">
        <MessageItem
          message={parentMessage}
          authorName={members[parentMessage.author_id] ?? "Unknown"}
          channelId={channelId}
          currentUserId={currentUserId}
          isThreaded
        />
      </div>

      {/* Replies */}
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading ? (
          <div className="space-y-3 px-4">
            {[1, 2].map((i) => (
              <div key={i} className="flex gap-3">
                <Skeleton className="h-7 w-7 rounded-full shrink-0" />
                <div className="space-y-1 flex-1">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-4 w-full" />
                </div>
              </div>
            ))}
          </div>
        ) : replies.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">No replies yet</p>
        ) : (
          replies.map((r, i) => {
            const prev = i > 0 ? replies[i - 1] : null
            const isGrouped =
              prev !== null &&
              prev.author_id === r.author_id &&
              Math.abs(new Date(r.created_at).getTime() - new Date(prev.created_at).getTime()) < 5 * 60 * 1000
            return (
              <MessageItem
                key={r.id}
                message={r}
                authorName={members[r.author_id] ?? "Unknown"}
                channelId={channelId}
                currentUserId={currentUserId}
                isGrouped={isGrouped}
                isThreaded
              />
            )
          })
        )}
      </div>

      {/* Reply composer */}
      <MessageComposer
        placeholder="Reply in thread…"
        workspaceId={workspaceId}
        members={memberList}
        onSend={(content) => reply({ content, thread_id: parentMessage.id })}
      />
    </div>
  )
}
