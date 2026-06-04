"use client"
import { useState, useRef, useEffect } from "react"
import { Send, Paperclip, X, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

interface Attachment {
  name: string
  url: string
}

interface MessageComposerProps {
  onSend: (content: string) => void
  placeholder?: string
  disabled?: boolean
  workspaceId?: string
  members?: Array<{ id: string; name: string }>  // for @mention autocomplete
}

export function MessageComposer({
  onSend,
  placeholder = "Message…",
  disabled,
  workspaceId,
  members = [],
}: MessageComposerProps) {
  const [content, setContent] = useState("")
  const [attachment, setAttachment] = useState<Attachment | null>(null)
  const [uploading, setUploading] = useState(false)
  // @mention autocomplete state
  const [mentionQuery, setMentionQuery] = useState<string | null>(null)
  const [mentionStart, setMentionStart] = useState(0)
  const [mentionIndex, setMentionIndex] = useState(0)
  const fileRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Filter members for autocomplete
  const mentionMatches =
    mentionQuery !== null
      ? members.filter((m) => m.name.toLowerCase().startsWith(mentionQuery.toLowerCase())).slice(0, 6)
      : []

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !workspaceId) return
    setUploading(true)
    const fd = new FormData()
    fd.append("file", file)
    api
      .post(`/files/upload?workspace_id=${workspaceId}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((res) => setAttachment({ name: res.data.name, url: res.data.url }))
      .catch(() => {})
      .finally(() => {
        setUploading(false)
        if (fileRef.current) fileRef.current.value = ""
      })
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value
    setContent(val)
    // Auto-resize
    const t = e.target
    t.style.height = "auto"
    t.style.height = Math.min(t.scrollHeight, 128) + "px"

    // @mention detection
    const cursor = t.selectionStart ?? val.length
    const textUpToCursor = val.slice(0, cursor)
    const match = textUpToCursor.match(/@(\w*)$/)
    if (match) {
      setMentionQuery(match[1])
      setMentionStart(cursor - match[0].length)
      setMentionIndex(0)
    } else {
      setMentionQuery(null)
    }
  }

  function insertMention(name: string) {
    const before = content.slice(0, mentionStart)
    const after = content.slice(mentionStart + (mentionQuery?.length ?? 0) + 1)
    const newContent = `${before}@${name} ${after}`
    setContent(newContent)
    setMentionQuery(null)
    setTimeout(() => {
      const t = textareaRef.current
      if (t) {
        const pos = before.length + name.length + 2
        t.setSelectionRange(pos, pos)
        t.focus()
        t.style.height = "auto"
        t.style.height = Math.min(t.scrollHeight, 128) + "px"
      }
    }, 0)
  }

  function handleSend() {
    let text = content.trim()
    if (!text && !attachment) return
    if (attachment) {
      const ext = attachment.name.split(".").pop()?.toLowerCase() ?? ""
      const isImage = ["jpg", "jpeg", "png", "gif", "webp", "svg"].includes(ext)
      const attachment_part = isImage
        ? `![${attachment.name}](${attachment.url})`
        : `[📎 ${attachment.name}](${attachment.url})`
      text = text ? `${text}\n${attachment_part}` : attachment_part
    }
    onSend(text)
    setContent("")
    setAttachment(null)
    setMentionQuery(null)
    if (textareaRef.current) textareaRef.current.style.height = "auto"
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Navigate + select @mention autocomplete
    if (mentionQuery !== null && mentionMatches.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setMentionIndex((i) => Math.min(i + 1, mentionMatches.length - 1))
        return
      }
      if (e.key === "ArrowUp") {
        e.preventDefault()
        setMentionIndex((i) => Math.max(i - 1, 0))
        return
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault()
        insertMention(mentionMatches[mentionIndex].name)
        return
      }
      if (e.key === "Escape") {
        setMentionQuery(null)
        return
      }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="mx-4 mb-4 relative">
      {/* Attachment preview */}
      {attachment && (
        <div className="flex items-center gap-2 mb-1.5 px-3 py-1.5 rounded-lg bg-muted/50 border text-xs">
          <span className="truncate flex-1 text-muted-foreground">📎 {attachment.name}</span>
          <button onClick={() => setAttachment(null)} className="text-muted-foreground hover:text-foreground">
            <X size={12} />
          </button>
        </div>
      )}

      {/* @mention dropdown */}
      {mentionQuery !== null && mentionMatches.length > 0 && (
        <div className="absolute bottom-full mb-1 left-0 z-50 bg-popover border rounded-xl shadow-lg overflow-hidden min-w-[180px]">
          {mentionMatches.map((m, i) => (
            <button
              key={m.id}
              onMouseDown={(e) => { e.preventDefault(); insertMention(m.name) }}
              className={cn(
                "flex items-center gap-2 w-full px-3 py-2 text-sm text-left transition-colors",
                i === mentionIndex ? "bg-accent/10 text-accent" : "hover:bg-muted"
              )}
            >
              <span className="h-5 w-5 rounded-full bg-accent text-white text-[10px] font-medium flex items-center justify-center shrink-0">
                {m.name[0].toUpperCase()}
              </span>
              {m.name}
            </button>
          ))}
        </div>
      )}

      {/* Composer box */}
      <div className="border rounded-xl bg-background flex items-end gap-2 px-3 py-2 focus-within:ring-1 focus-within:ring-accent/50 transition-shadow">
        <input type="file" ref={fileRef} className="hidden" onChange={handleFileChange} />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading || !workspaceId}
          title="Attach file"
          className="text-muted-foreground hover:text-foreground transition-colors p-1 shrink-0 disabled:opacity-40"
        >
          {uploading ? <Loader2 size={16} className="animate-spin" /> : <Paperclip size={16} />}
        </button>
        <textarea
          ref={textareaRef}
          value={content}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground min-h-[24px] max-h-32"
        />
        <button
          onClick={handleSend}
          disabled={(!content.trim() && !attachment) || disabled}
          className={cn(
            "shrink-0 p-1 rounded transition-colors",
            content.trim() || attachment ? "text-accent hover:text-accent/80" : "text-muted-foreground/40"
          )}
        >
          <Send size={16} />
        </button>
      </div>

      {/* Keyboard hints */}
      <div className="flex gap-3 mt-1 px-1">
        <span className="text-[10px] text-muted-foreground/50">Enter to send · Shift+Enter for new line · @name to mention</span>
      </div>
    </div>
  )
}
