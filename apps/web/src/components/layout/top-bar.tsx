"use client"
import { Moon, Sun, LogOut, Menu, Search, UserCircle } from "lucide-react"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"
import { useAuthStore } from "@/store/auth"
import { useRouter } from "next/navigation"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { NotificationPanel } from "@/components/notifications/notification-panel"

interface TopBarProps {
  onMenuClick?: () => void
  onSearchClick?: () => void
  workspaceId?: string
}

export function TopBar({ onMenuClick, onSearchClick, workspaceId }: TopBarProps) {
  const { theme, setTheme } = useTheme()
  const { user, clearAuth } = useAuthStore()
  const router = useRouter()

  function logout() {
    clearAuth()
    router.push("/login")
  }

  return (
    <>
      <header className="h-14 border-b flex items-center justify-between px-4 shrink-0 relative z-20">
        <div className="flex items-center gap-2">
          {onMenuClick && (
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={onMenuClick}
              aria-label="Open menu"
            >
              <Menu size={20} />
            </Button>
          )}

          {onSearchClick && (
            <Button
              variant="ghost"
              size="sm"
              className="hidden sm:flex items-center gap-2 text-muted-foreground hover:text-foreground px-3"
              onClick={onSearchClick}
            >
              <Search size={14} />
              <span className="text-sm">Search</span>
              <kbd className="ml-2 hidden lg:inline-flex text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded border">
                ⌘K
              </kbd>
            </Button>
          )}
          {onSearchClick && (
            <Button
              variant="ghost"
              size="icon"
              className="sm:hidden"
              onClick={onSearchClick}
              aria-label="Search"
            >
              <Search size={18} />
            </Button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </Button>
          <NotificationPanel />
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon" className="rounded-full" />}
            >
              <Avatar className="h-7 w-7">
                <AvatarFallback className="text-xs bg-accent text-white">
                  {user?.name?.[0]?.toUpperCase() ?? "U"}
                </AvatarFallback>
              </Avatar>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem className="text-sm text-muted-foreground">
                {user?.email}
              </DropdownMenuItem>
              {workspaceId && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => router.push(`/workspace/${workspaceId}/profile`)}>
                    <UserCircle size={14} className="mr-2" /> Profile settings
                  </DropdownMenuItem>
                </>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout} className="text-destructive">
                <LogOut size={14} className="mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
    </>
  )
}
