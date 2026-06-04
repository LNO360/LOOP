"use client"
import { use, useState, useEffect } from "react"
import { Sidebar } from "@/components/layout/sidebar"
import { TopBar } from "@/components/layout/top-bar"
import { SearchPalette } from "@/components/search/search-palette"

export default function WorkspaceLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = use(params)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)

  // Cmd+K / Ctrl+K global shortcut
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setSearchOpen((o) => !o)
      }
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar — always visible on md+ */}
      <div className="hidden md:flex">
        <Sidebar workspaceId={workspaceId} />
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full z-50">
            <Sidebar
              workspaceId={workspaceId}
              onNavigate={() => setSidebarOpen(false)}
            />
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <TopBar
          onMenuClick={() => setSidebarOpen((o) => !o)}
          onSearchClick={() => setSearchOpen(true)}
          workspaceId={workspaceId}
        />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>

      {/* Global search palette */}
      {searchOpen && (
        <SearchPalette
          workspaceId={workspaceId}
          onClose={() => setSearchOpen(false)}
        />
      )}
    </div>
  )
}
