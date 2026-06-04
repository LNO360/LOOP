import { create } from "zustand"
import { persist } from "zustand/middleware"

interface AuthUser {
  id: string
  email: string
  name: string
  avatar_url?: string
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  workspaceId: string | null
  _hasHydrated: boolean
  setAuth: (token: string, user: AuthUser, workspaceId: string) => void
  clearAuth: () => void
  setHasHydrated: () => void
}

function syncTokenToStorage(token: string | null) {
  if (typeof window === "undefined") return
  if (token) localStorage.setItem("lno_token", token)
  else localStorage.removeItem("lno_token")
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      workspaceId: null,
      _hasHydrated: false,
      setAuth: (token, user, workspaceId) => {
        syncTokenToStorage(token)
        set({ token, user, workspaceId })
      },
      clearAuth: () => {
        syncTokenToStorage(null)
        set({ token: null, user: null, workspaceId: null })
      },
      setHasHydrated: () => set({ _hasHydrated: true }),
    }),
    {
      name: "lno-auth",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        workspaceId: state.workspaceId,
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.token) syncTokenToStorage(state.token)
        state?.setHasHydrated()
      },
    }
  )
)

/** Call once at app shell mount so persist finishes before auth redirects. */
export function rehydrateAuthStore() {
  if (useAuthStore.getState()._hasHydrated) return
  if (useAuthStore.persist.hasHydrated()) {
    useAuthStore.getState().setHasHydrated()
    return
  }
  void useAuthStore.persist.rehydrate()
}
