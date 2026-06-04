import { useMutation } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useAuthStore } from "@/store/auth"

export function useUpdateProfile() {
  const { user, token, workspaceId, setAuth } = useAuthStore()
  return useMutation({
    mutationFn: (data: { name?: string; avatar_url?: string }) =>
      api.patch("/users/me", data).then((r) => r.data),
    onSuccess: (updated) => {
      // Update the Zustand store so the UI reflects changes immediately
      if (user && token && workspaceId) {
        setAuth(token, { ...user, ...updated }, workspaceId)
      }
    },
  })
}
