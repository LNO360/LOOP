"use client"
import { useState } from "react"
import { useCreateChannel } from "@/hooks/use-channels"
import { useRouter } from "next/navigation"
import { Hash, Lock, X, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface CreateChannelDialogProps {
  workspaceId: string
  onClose: () => void
}

export function CreateChannelDialog({ workspaceId, onClose }: CreateChannelDialogProps) {
  const [name, setName] = useState("")
  const [isPrivate, setIsPrivate] = useState(false)
  const { mutateAsync, isPending } = useCreateChannel(workspaceId)
  const router = useRouter()

  function sanitizeName(val: string) {
    return val.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const slug = sanitizeName(name)
    if (!slug) return
    try {
      const ch = await mutateAsync({ name: slug, type: isPrivate ? "private" : "public" })
      onClose()
      router.push(`/workspace/${workspaceId}/channel/${ch.id}`)
    } catch {}
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-background border rounded-2xl shadow-xl p-6 w-full max-w-md mx-4">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-semibold text-base">Create a channel</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors">
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Channel name</label>
            <div className="flex items-center gap-2 border rounded-xl px-3 py-2 focus-within:ring-1 focus-within:ring-accent/50 bg-muted/30">
              <Hash size={14} className="text-muted-foreground shrink-0" />
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. engineering"
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/60"
              />
            </div>
            {name && (
              <p className="text-xs text-muted-foreground">
                Will be created as <span className="font-mono text-foreground">#{sanitizeName(name)}</span>
              </p>
            )}
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-2 block">Visibility</label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { value: false, icon: Hash, label: "Public", desc: "Anyone in workspace" },
                { value: true, icon: Lock, label: "Private", desc: "Invite only" },
              ].map(({ value, icon: Icon, label, desc }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => setIsPrivate(value)}
                  className={cn(
                    "flex items-start gap-2 p-3 rounded-xl border text-left transition-colors",
                    isPrivate === value ? "border-accent/50 bg-accent/5" : "hover:bg-muted/50"
                  )}
                >
                  <Icon size={14} className={cn("mt-0.5 shrink-0", isPrivate === value ? "text-accent" : "text-muted-foreground")} />
                  <div>
                    <p className={cn("text-xs font-medium", isPrivate === value && "text-accent")}>{label}</p>
                    <p className="text-[10px] text-muted-foreground">{desc}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-colors">
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || isPending}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-accent text-white rounded-lg hover:bg-accent/90 disabled:opacity-50 transition-colors"
            >
              {isPending ? <Loader2 size={13} className="animate-spin" /> : null}
              Create channel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
