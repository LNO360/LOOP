"use client"
import { useEffect, useRef, useState } from "react"
import { MessageItem } from "./message-item"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowDown } from "lucide-react"
import { format, isToday, isYesterday, isSameDay, isSameMinute } from "date-fns"
import { cn } from "@/lib/utils"
import type { Message } from "@/hooks/use-messages"

function DateDivider({ date }: { date: Date }) {
  let label: string
  if (isToday(date)) label = "Today"
  else if (isYesterday(date)) label = "Yesterday"
  else label = format(date, "EEEE, MMMM d")

  return (
    <div className="flex items-center gap-3 px-4 py-3 select-none">
      <div className="flex-1 h-px bg-border" />
      <span className="text-[11px] text-muted-foreground font-medium">{label}</span>
      <div className="flex-1 h-px bg-border" />
    </div>
  )
}

interface MessageFeedProps {
  messages: Message[]
  isLoading: boolean
  members: Record<string, string>
  currentUserId: string
  channelId: string
  pinnedMessageIds?: Set<string>
  onThreadClick: (msg: Message) => void
  onCreateTask: (msg: Message) => void
}

export function MessageFeed({
  messages,
  isLoading,
  members,
  currentUserId,
  channelId,
  pinnedMessageIds,
  onThreadClick,
  onCreateTask,
}: MessageFeedProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [showJumpToBottom, setShowJumpToBottom] = useState(false)

  // Auto-scroll on new messages only if near bottom
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const distFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    if (distFromBottom < 200) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }, [messages])

  // Track scroll to show/hide jump button
  function handleScroll() {
    const container = containerRef.current
    if (!container) return
    const distFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    setShowJumpToBottom(distFromBottom > 300)
  }

  function jumpToBottom() {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    setShowJumpToBottom(false)
  }

  if (isLoading) {
    return (
      <div className="flex-1 p-4 space-y-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex gap-3">
            <Skeleton className="h-8 w-8 rounded-full shrink-0" />
            <div className="space-y-1.5 flex-1">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-4 w-full max-w-sm" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!messages.length) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-muted-foreground">No messages yet. Say hello! 👋</p>
      </div>
    )
  }

  // Build render items with date dividers + grouping
  type Item =
    | { type: "date"; date: Date; key: string }
    | { type: "message"; msg: Message; isGrouped: boolean; key: string }

  const items: Item[] = []
  let lastDate: Date | null = null
  let lastAuthorId: string | null = null
  let lastTimestamp: Date | null = null

  for (const msg of messages) {
    const msgDate = new Date(msg.created_at)

    // Date divider
    if (!lastDate || !isSameDay(lastDate, msgDate)) {
      items.push({ type: "date", date: msgDate, key: `date-${msgDate.toDateString()}` })
      lastDate = msgDate
      lastAuthorId = null  // reset grouping on date boundary
      lastTimestamp = null
    }

    // Grouping: same author within 5 minutes = grouped (no avatar/name)
    const grouped =
      lastAuthorId === msg.author_id &&
      lastTimestamp !== null &&
      Math.abs(msgDate.getTime() - lastTimestamp.getTime()) < 5 * 60 * 1000

    items.push({ type: "message", msg, isGrouped: grouped, key: msg.id })
    lastAuthorId = msg.author_id
    lastTimestamp = msgDate
  }

  return (
    <div className="relative flex-1 min-h-0">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto py-2"
      >
        {items.map((item) =>
          item.type === "date" ? (
            <DateDivider key={item.key} date={item.date} />
          ) : (
            <MessageItem
              key={item.key}
              message={item.msg}
              authorName={members[item.msg.author_id] ?? "Unknown"}
              channelId={channelId}
              currentUserId={currentUserId}
              isGrouped={item.isGrouped}
              isPinned={pinnedMessageIds?.has(item.msg.id)}
              onThreadClick={onThreadClick}
              onCreateTask={onCreateTask}
            />
          )
        )}
        <div ref={bottomRef} className="h-2" />
      </div>

      {/* Jump to bottom button */}
      {showJumpToBottom && (
        <button
          onClick={jumpToBottom}
          className={cn(
            "absolute bottom-4 left-1/2 -translate-x-1/2 z-10",
            "flex items-center gap-1.5 px-3 py-1.5 rounded-full",
            "bg-accent text-white text-xs font-medium shadow-lg",
            "hover:bg-accent/90 transition-colors animate-in fade-in slide-in-from-bottom-2"
          )}
        >
          <ArrowDown size={12} /> Jump to latest
        </button>
      )}
    </div>
  )
}
