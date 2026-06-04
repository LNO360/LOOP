"use client"

import { useEffect } from "react"
import { rehydrateAuthStore, useAuthStore } from "@/store/auth"

/** True after zustand has loaded auth from localStorage (safe to check token). */
export function useAuthHydrated(): boolean {
  const hasHydrated = useAuthStore((s) => s._hasHydrated)

  useEffect(() => {
    rehydrateAuthStore()
    const unsub = useAuthStore.persist.onFinishHydration(() => {
      useAuthStore.getState().setHasHydrated()
    })
    return unsub
  }, [])

  return hasHydrated
}
