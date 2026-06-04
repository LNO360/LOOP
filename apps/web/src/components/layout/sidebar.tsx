"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  CheckSquare, FileText, LayoutDashboard, ChevronDown,
  Hash, Plus, MessageCircle, FolderOpen, Settings, Bot, DollarSign, Users, Plug, LineChart,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useState } from "react"
import { useDMs } from "@/hooks/use-dms"
import { useAuthStore } from "@/store/auth"
import { NewDMDialog } from "@/components/messaging/new-dm-dialog"
import { CreateChannelDialog } from "@/components/channels/create-channel-dialog"

interface SidebarProps {
  workspaceId: string
  onNavigate?: () => void
}

export function Sidebar({ workspaceId, onNavigate }: SidebarProps) {
  const pathname = usePathname()
  const [channelsOpen, setChannelsOpen] = useState(true)
  const [dmsOpen, setDmsOpen] = useState(true)
  const [dmDialogOpen, setDmDialogOpen] = useState(false)
  const [createChannelOpen, setCreateChannelOpen] = useState(false)
  const user = useAuthStore((s) => s.user)

  const { data: channels = [] } = useQuery({
    queryKey: ["channels", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/channels`).then((r) => r.data),
  })

  const { data: dms = [] } = useDMs(workspaceId)

  const nav = [
    { href: `/workspace/${workspaceId}`, icon: LayoutDashboard, label: "Dashboard", exact: true },
    { href: `/workspace/${workspaceId}/tasks`, icon: CheckSquare, label: "Tasks" },
    { href: `/workspace/${workspaceId}/projects`, icon: FolderOpen, label: "Projects" },
    { href: `/workspace/${workspaceId}/docs`, icon: FileText, label: "Docs" },
    { href: `/workspace/${workspaceId}/agents`, icon: Bot, label: "AI Work" },
    { href: `/workspace/${workspaceId}/boardroom`, icon: Users, label: "Boardroom" },
    { href: `/workspace/${workspaceId}/finance`, icon: DollarSign, label: "Finance" },
    { href: `/workspace/${workspaceId}/seo`, icon: LineChart, label: "SEO" },
    { href: `/workspace/${workspaceId}/settings`, icon: Settings, label: "Settings" },
  ]

  const isNavActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/")

  return (
    <aside className="w-64 border-r border-border/60 bg-sidebar flex flex-col shrink-0">
      <div className="border-b border-border/60 px-4 py-4">
        <div className="rounded-[20px] border border-border/50 bg-sidebar-accent/60 px-3 py-3">
          <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">Workspace</p>
          <div className="mt-2 flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <svg width="64" height="20" viewBox="0 0 64 20" fill="none" xmlns="http://www.w3.org/2000/svg" className="text-foreground">
                <text x="0" y="16" fontFamily="var(--font-sans), system-ui" fontSize="16" fontWeight="600" letterSpacing="-0.03em" fill="currentColor">loop</text>
              </svg>
            </div>
          </div>
        </div>
      </div>
      <ScrollArea className="flex-1 py-2">
        <nav className="px-3 space-y-1">
          {nav.map(({ href, icon: Icon, label, exact }) => (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-2xl text-sm transition-all",
                isNavActive(href, exact)
                  ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
              )}
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}
        </nav>

        {/* Channels */}
        <div className="mt-5 px-3">
          <div className="flex items-center px-2 py-1">
            <button
              onClick={() => setChannelsOpen((o) => !o)}
              className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground uppercase tracking-[0.22em] hover:text-foreground transition-colors"
            >
              <ChevronDown size={12} className={cn("transition-transform", !channelsOpen && "-rotate-90")} />
              Channels
            </button>
            <button
              onClick={() => setCreateChannelOpen(true)}
              className="ml-auto p-0.5 rounded hover:bg-sidebar-accent text-muted-foreground hover:text-foreground transition-colors"
              title="Create channel"
            >
              <Plus size={12} />
            </button>
          </div>
          {channelsOpen && (
            <div className="mt-2 space-y-1">
              {(channels as Array<{ id: string; name: string }>).map((ch) => (
                <Link
                  key={ch.id}
                  href={`/workspace/${workspaceId}/channel/${ch.id}`}
                  onClick={onNavigate}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 rounded-xl text-sm transition-colors",
                    pathname.includes(ch.id)
                      ? "bg-sidebar-accent text-foreground"
                      : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
                  )}
                >
                  <Hash size={14} />
                  {ch.name}
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Direct Messages */}
        <div className="mt-5 px-3">
          <button
            onClick={() => setDmsOpen((o) => !o)}
            className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground uppercase tracking-[0.22em] px-2 py-1 w-full hover:text-foreground transition-colors"
          >
            <ChevronDown size={12} className={cn("transition-transform", !dmsOpen && "-rotate-90")} />
            Direct Messages
          </button>
          {dmsOpen && (
            <div className="mt-2 space-y-1">
              {(dms as Array<{ id: string; other_user_name?: string }>).map((dm) => (
                <Link
                  key={dm.id}
                  href={`/workspace/${workspaceId}/dm/${dm.id}`}
                  onClick={onNavigate}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 rounded-xl text-sm transition-colors",
                    pathname.includes(dm.id)
                      ? "bg-sidebar-accent text-foreground"
                      : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
                  )}
                >
                  <MessageCircle size={14} />
                  {dm.other_user_name ?? "DM"}
                </Link>
              ))}
              <button
                onClick={() => setDmDialogOpen(true)}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-foreground transition-colors w-full text-left"
              >
                <Plus size={14} />
                New message
              </button>
            </div>
          )}
        </div>
      </ScrollArea>

      {dmDialogOpen && (
        <NewDMDialog
          workspaceId={workspaceId}
          currentUserId={user?.id ?? ""}
          onClose={() => setDmDialogOpen(false)}
        />
      )}
      {createChannelOpen && (
        <CreateChannelDialog workspaceId={workspaceId} onClose={() => setCreateChannelOpen(false)} />
      )}
    </aside>
  )
}
