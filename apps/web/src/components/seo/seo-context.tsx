"use client"
import { createContext, useContext } from "react"

interface SeoContextValue {
  workspaceId: string
  siteUrl: string | null
  /** False until localStorage GSC site has been read on the client. */
  siteReady: boolean
  selectSite: (url: string) => void
}

const SeoContext = createContext<SeoContextValue | null>(null)

export function SeoProvider({
  children,
  workspaceId,
  siteUrl,
  siteReady,
  selectSite,
}: {
  children: React.ReactNode
  workspaceId: string
  siteUrl: string | null
  siteReady: boolean
  selectSite: (url: string) => void
}) {
  return (
    <SeoContext.Provider value={{ workspaceId, siteUrl, siteReady, selectSite }}>
      {children}
    </SeoContext.Provider>
  )
}

export function useSeoContext() {
  const ctx = useContext(SeoContext)
  if (!ctx) throw new Error("useSeoContext must be used within SeoProvider")
  return ctx
}
