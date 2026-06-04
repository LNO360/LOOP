"use client"
import { useState, useRef, useEffect } from "react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { formatDistanceToNow, format } from "date-fns"
import { MessageSquare, Plus, MoreHorizontal, Pencil, Trash2, Check, X, Smile, Pin } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Message, Reaction } from "@/hooks/use-messages"
import { useEditMessage, useDeleteMessage, useAddReaction, useRemoveReaction, usePinMessage, useUnpinMessage } from "@/hooks/use-messages"

// ── Quick emoji set ──────────────────────────────────────────
const QUICK_EMOJIS = ["👍", "❤️", "😂", "🔥", "✅", "👀"]

// ── Rich text renderer ───────────────────────────────────────
function RichText({ content }: { content: string }) {
  // Parse the content and render markdown-lite + @mentions
  const lines = content.split("\n")
  const elements: React.ReactNode[] = []
  let inCodeBlock = false
  let codeLines: string[] = []
  let codeKey = 0

  function flushCode() {
    if (codeLines.length) {
      elements.push(
        <pre key={`code-${codeKey++}`} className="my-2 rounded-lg bg-muted/80 border px-3 py-2 text-xs font-mono overflow-x-auto leading-relaxed">
          <code>{codeLines.join("\n")}</code>
        </pre>
      )
      codeLines = []
    }
  }

  function renderInline(text: string, keyPrefix: string): React.ReactNode {
    // Handle image markdown
    const imageMatch = text.match(/^!\[([^\]]*)\]\(([^)]+)\)$/)
    if (imageMatch) {
      return (
        <img
          key={keyPrefix}
          src={imageMatch[2]}
          alt={imageMatch[1]}
          className="max-w-xs max-h-48 rounded-lg object-cover border mt-1"
          onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
        />
      )
    }
    // Handle file link markdown [📎 name](url)
    const fileMatch = text.match(/^\[📎 ([^\]]+)\]\(([^)]+)\)$/)
    if (fileMatch) {
      return (
        <a key={keyPrefix} href={fileMatch[2]} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted hover:bg-muted/80 transition-colors text-xs font-medium border">
          📎 {fileMatch[1]}
        </a>
      )
    }

    // Inline patterns: **bold**, *italic*, `code`, @mention
    const pattern = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`|@\w+)/g
    const parts: React.ReactNode[] = []
    let last = 0
    let match: RegExpExecArray | null

    while ((match = pattern.exec(text)) !== null) {
      if (match.index > last) parts.push(text.slice(last, match.index))
      const full = match[0]
      if (full.startsWith("**")) {
        parts.push(<strong key={match.index}>{match[2]}</strong>)
      } else if (full.startsWith("*")) {
        parts.push(<em key={match.index}>{match[3]}</em>)
      } else if (full.startsWith("`")) {
        parts.push(
          <code key={match.index} className="bg-muted/70 border rounded px-1 py-0.5 text-[11px] font-mono">
            {match[4]}
          </code>
        )
      } else if (full.startsWith("@")) {
        parts.push(
          <span key={match.index} className="text-accent font-medium bg-accent/10 rounded px-0.5">
            {full}
          </span>
        )
      }
      last = match.index + full.length
    }
    if (last < text.length) parts.push(text.slice(last))
    return <>{parts}</>
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line.startsWith("```")) {
      if (inCodeBlock) {
        flushCode()
        inCodeBlock = false
      } else {
        inCodeBlock = true
      }
      continue
    }
    if (inCodeBlock) {
      codeLines.push(line)
      continue
    }
    elements.push(
      <p key={i} className="leading-relaxed min-h-[1.2em] empty:hidden">
        {renderInline(line, `l${i}`)}
      </p>
    )
  }
  if (inCodeBlock) flushCode()

  return <div className="text-sm space-y-0.5">{elements}</div>
}

// ── Reaction bubble ──────────────────────────────────────────
function ReactionBubble({
  reaction,
  currentUserId,
  onToggle,
}: {
  reaction: Reaction
  currentUserId: string
  onToggle: (emoji: string, myReaction: boolean) => void
}) {
  const mine = reaction.user_ids.includes(currentUserId)
  return (
    <button
      onClick={() => onToggle(reaction.emoji, mine)}
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border text-xs transition-colors select-none",
        mine
          ? "bg-accent/15 border-accent/40 text-accent font-medium"
          : "bg-muted/50 border-transparent hover:border-muted-foreground/20 text-foreground/70 hover:text-foreground"
      )}
    >
      <span>{reaction.emoji}</span>
      <span className="text-[10px] tabular-nums">{reaction.count}</span>
    </button>
  )
}

// ── Emoji picker ─────────────────────────────────────────────
function EmojiPicker({
  onSelect,
  onClose,
}: {
  onSelect: (emoji: string) => void
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [onClose])

  return (
    <div
      ref={ref}
      className="absolute bottom-full mb-1 right-0 z-50 flex items-center gap-1 bg-popover border rounded-xl shadow-lg px-2 py-1.5"
    >
      {QUICK_EMOJIS.map((emoji) => (
        <button
          key={emoji}
          onClick={() => { onSelect(emoji); onClose() }}
          className="text-lg hover:scale-125 transition-transform p-0.5 rounded"
        >
          {emoji}
        </button>
      ))}
    </div>
  )
}

// ── Action menu ──────────────────────────────────────────────
function ActionMenu({
  onEdit,
  onDelete,
  onClose,
}: {
  onEdit: () => void
  onDelete: () => void
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [onClose])

  return (
    <div
      ref={ref}
      className="absolute bottom-full mb-1 right-0 z-50 bg-popover border rounded-xl shadow-lg overflow-hidden min-w-[120px]"
    >
      <button
        onClick={() => { onEdit(); onClose() }}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs hover:bg-muted transition-colors"
      >
        <Pencil size={12} /> Edit
      </button>
      <button
        onClick={() => { onDelete(); onClose() }}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs text-destructive hover:bg-destructive/10 transition-colors"
      >
        <Trash2 size={12} /> Delete
      </button>
    </div>
  )
}

// ── MessageItem ──────────────────────────────────────────────
interface MessageItemProps {
  message: Message
  authorName: string
  channelId: string
  currentUserId: string
  isGrouped?: boolean    // consecutive msg from same author → hide avatar + name
  isThreaded?: boolean
  isPinned?: boolean
  onThreadClick?: (message: Message) => void
  onCreateTask?: (message: Message) => void
}

export function MessageItem({
  message,
  authorName,
  channelId,
  currentUserId,
  isGrouped,
  isThreaded,
  isPinned,
  onThreadClick,
  onCreateTask,
}: MessageItemProps) {
  const [showPicker, setShowPicker] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState(message.content)
  const editRef = useRef<HTMLTextAreaElement>(null)

  const { mutate: addReaction } = useAddReaction(channelId)
  const { mutate: removeReaction } = useRemoveReaction(channelId)
  const { mutate: editMessage, isPending: editPending } = useEditMessage(channelId)
  const { mutate: deleteMessage } = useDeleteMessage(channelId)
  const { mutate: pinMsg } = usePinMessage(channelId)
  const { mutate: unpinMsg } = useUnpinMessage(channelId)

  const isOwn = message.author_id === currentUserId
  const initials = authorName?.[0]?.toUpperCase() ?? "U"
  const time = formatDistanceToNow(new Date(message.created_at), { addSuffix: true })

  useEffect(() => {
    if (editing) editRef.current?.focus()
  }, [editing])

  function handleReactionToggle(emoji: string, mine: boolean) {
    if (mine) {
      removeReaction({ messageId: message.id, emoji })
    } else {
      addReaction({ messageId: message.id, emoji })
    }
  }

  function handleEmojiSelect(emoji: string) {
    const existing = message.reactions.find((r) => r.emoji === emoji)
    const mine = existing?.user_ids.includes(currentUserId) ?? false
    if (mine) {
      removeReaction({ messageId: message.id, emoji })
    } else {
      addReaction({ messageId: message.id, emoji })
    }
  }

  function handleEditSubmit() {
    const trimmed = editContent.trim()
    if (!trimmed || trimmed === message.content) {
      setEditing(false)
      return
    }
    editMessage(
      { messageId: message.id, content: trimmed },
      { onSuccess: () => setEditing(false) }
    )
  }

  function handleEditKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleEditSubmit() }
    if (e.key === "Escape") { setEditing(false); setEditContent(message.content) }
  }

  return (
    <div className={cn(
      "group relative flex gap-3 px-4 hover:bg-muted/30 transition-colors",
      isGrouped ? "py-0.5" : "py-1.5 mt-1"
    )}>
      {/* Avatar or spacer */}
      <div className="w-8 shrink-0 flex justify-center">
        {!isGrouped ? (
          <Avatar className="h-8 w-8 mt-0.5">
            <AvatarFallback className="text-xs bg-accent text-white">{initials}</AvatarFallback>
          </Avatar>
        ) : (
          <span className="text-[9px] text-muted-foreground/0 group-hover:text-muted-foreground/50 mt-1 leading-none transition-colors select-none w-full text-center">
            {format(new Date(message.created_at), "HH:mm")}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Name + time — only for first message in group */}
        {!isGrouped && (
          <div className="flex items-baseline gap-2 mb-0.5">
            <span className="text-sm font-semibold leading-none">{authorName}</span>
            <span className="text-[10px] text-muted-foreground">{time}</span>
            {message.edited_at && (
              <span className="text-[9px] text-muted-foreground/60 italic">(edited)</span>
            )}
          </div>
        )}

        {/* Edit mode */}
        {editing ? (
          <div className="space-y-1.5">
            <textarea
              ref={editRef}
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              onKeyDown={handleEditKeyDown}
              rows={Math.max(1, editContent.split("\n").length)}
              className="w-full resize-none bg-muted/50 border border-accent/40 rounded-lg px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-accent/50 max-h-48 overflow-y-auto"
            />
            <div className="flex items-center gap-2 text-xs">
              <button
                onClick={handleEditSubmit}
                disabled={editPending}
                className="flex items-center gap-1 px-2 py-1 rounded-md bg-accent text-white hover:bg-accent/90 disabled:opacity-50 transition-colors"
              >
                <Check size={11} /> Save
              </button>
              <button
                onClick={() => { setEditing(false); setEditContent(message.content) }}
                className="flex items-center gap-1 px-2 py-1 rounded-md bg-muted hover:bg-muted/80 transition-colors"
              >
                <X size={11} /> Cancel
              </button>
              <span className="text-muted-foreground">Esc to cancel · Enter to save</span>
            </div>
          </div>
        ) : (
          <RichText content={message.content} />
        )}

        {/* Reactions */}
        {message.reactions.length > 0 && !editing && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {message.reactions.map((r) => (
              <ReactionBubble
                key={r.emoji}
                reaction={r}
                currentUserId={currentUserId}
                onToggle={handleReactionToggle}
              />
            ))}
          </div>
        )}
      </div>

      {/* Hover action bar */}
      {!editing && (
        <div className="absolute right-4 top-0 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5 bg-background border rounded-lg shadow-sm px-1 py-0.5 z-10">
          <div className="relative">
            <button
              onClick={() => { setShowPicker((v) => !v); setShowMenu(false) }}
              title="React"
              className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            >
              <Smile size={14} />
            </button>
            {showPicker && <EmojiPicker onSelect={handleEmojiSelect} onClose={() => setShowPicker(false)} />}
          </div>
          <button
            onClick={() => isPinned ? unpinMsg(message.id) : pinMsg(message.id)}
            title={isPinned ? "Unpin message" : "Pin message"}
            className={cn(
              "p-1 rounded hover:bg-muted transition-colors",
              isPinned ? "text-accent" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Pin size={14} />
          </button>
          {!isThreaded && (
            <button
              onClick={() => onThreadClick?.(message)}
              title="Reply in thread"
              className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            >
              <MessageSquare size={14} />
            </button>
          )}
          <button
            onClick={() => onCreateTask?.(message)}
            title="Create task"
            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            <Plus size={14} />
          </button>
          {isOwn && (
            <div className="relative">
              <button
                onClick={() => { setShowMenu((v) => !v); setShowPicker(false) }}
                title="More"
                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              >
                <MoreHorizontal size={14} />
              </button>
              {showMenu && (
                <ActionMenu
                  onEdit={() => { setEditing(true); setEditContent(message.content) }}
                  onDelete={() => deleteMessage(message.id)}
                  onClose={() => setShowMenu(false)}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
