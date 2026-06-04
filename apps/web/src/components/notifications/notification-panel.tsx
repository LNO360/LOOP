"use client"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Button } from "@/components/ui/button"
import { Bell, Check } from "lucide-react"
import { useNotifications, useMarkAllRead, useMarkRead } from "@/hooks/use-notifications"
import { ScrollArea } from "@/components/ui/scroll-area"
import { formatDistanceToNow } from "date-fns"
import { cn } from "@/lib/utils"

interface Notification {
  id: string
  message: string
  read: boolean
  created_at: string
}

interface NotifData {
  notifications: Notification[]
  unread_count: number
}

export function NotificationPanel() {
  const { data } = useNotifications()
  const { mutate: markAllRead } = useMarkAllRead()
  const { mutate: markRead } = useMarkRead()

  const notifData = data as NotifData | undefined
  const notifications = notifData?.notifications ?? []
  const unreadCount = notifData?.unread_count ?? 0

  return (
    <Popover>
      <PopoverTrigger render={<Button variant="ghost" size="icon" className="relative" />}>
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 h-4 w-4 text-[10px] font-bold bg-accent text-white rounded-full flex items-center justify-center pointer-events-none">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <span className="font-medium text-sm">Notifications</span>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-xs h-7"
              onClick={() => markAllRead()}
            >
              <Check size={12} className="mr-1" /> Mark all read
            </Button>
          )}
        </div>
        <ScrollArea className="max-h-80">
          {!notifications.length ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              All caught up! 🎉
            </p>
          ) : (
            notifications.map((n) => (
              <button
                key={n.id}
                onClick={() => markRead(n.id)}
                className={cn(
                  "w-full text-left px-4 py-3 border-b last:border-0 hover:bg-muted/30 transition-colors",
                  !n.read && "bg-accent/5"
                )}
              >
                <div className="flex items-start gap-2">
                  {!n.read && (
                    <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-accent shrink-0" />
                  )}
                  <div className={cn(!n.read ? "ml-0" : "ml-3.5")}>
                    <p className="text-sm leading-snug">{n.message}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                    </p>
                  </div>
                </div>
              </button>
            ))
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  )
}
