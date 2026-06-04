"use client"
import { use, useState } from "react"
import { useAuthStore } from "@/store/auth"
import { useUpdateProfile } from "@/hooks/use-profile"
import { User, Check, Loader2 } from "lucide-react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

export default function ProfilePage({ params }: { params: Promise<{ workspaceId: string }> }) {
  use(params) // needed for Next.js 16
  const user = useAuthStore((s) => s.user)
  const [name, setName] = useState(user?.name ?? "")
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url ?? "")
  const [saved, setSaved] = useState(false)
  const { mutateAsync, isPending } = useUpdateProfile()

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    await mutateAsync({ name: name.trim(), avatar_url: avatarUrl.trim() || undefined })
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="h-14 border-b flex items-center gap-2 px-6 shrink-0">
        <User size={16} className="text-muted-foreground" />
        <span className="font-medium text-sm">Profile Settings</span>
      </div>
      <div className="flex-1 p-6 max-w-lg mx-auto w-full space-y-8">
        {/* Avatar preview */}
        <div className="flex flex-col items-center gap-3">
          <Avatar className="h-20 w-20">
            {avatarUrl && <AvatarImage src={avatarUrl} alt={name} />}
            <AvatarFallback className="text-2xl bg-accent text-white">
              {name?.[0]?.toUpperCase() ?? "U"}
            </AvatarFallback>
          </Avatar>
          <p className="text-sm font-medium">{name || user?.name}</p>
          <p className="text-xs text-muted-foreground">{user?.email}</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSave} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Display name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border rounded-xl px-3 py-2 text-sm bg-background outline-none focus:ring-1 focus:ring-accent/50"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Avatar URL</label>
            <input
              value={avatarUrl}
              onChange={(e) => setAvatarUrl(e.target.value)}
              placeholder="https://..."
              className="w-full border rounded-xl px-3 py-2 text-sm bg-background outline-none focus:ring-1 focus:ring-accent/50"
            />
          </div>
          <button
            type="submit"
            disabled={isPending}
            className="flex items-center gap-2 px-5 py-2 bg-accent text-white rounded-xl text-sm hover:bg-accent/90 disabled:opacity-50 transition-colors"
          >
            {isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : saved ? (
              <Check size={14} />
            ) : null}
            {saved ? "Saved!" : "Save changes"}
          </button>
        </form>
      </div>
    </div>
  )
}
