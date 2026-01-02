import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { User, LoginCredentials } from "@/types"
import { authApi } from "@/api/client"

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  login: (credentials: LoginCredentials) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (credentials: LoginCredentials) => {
        set({ isLoading: true, error: null })
        try {
          const tokens = await authApi.login(credentials)
          localStorage.setItem("access_token", tokens.access_token)
          localStorage.setItem("refresh_token", tokens.refresh_token)

          const user = await authApi.getMe()
          set({ user, isAuthenticated: true, isLoading: false })
        } catch (error) {
          const message =
            error instanceof Error ? error.message : "Login failed"
          set({ error: message, isLoading: false })
          throw error
        }
      },

      logout: async () => {
        try {
          await authApi.logout()
        } finally {
          localStorage.removeItem("access_token")
          localStorage.removeItem("refresh_token")
          set({ user: null, isAuthenticated: false })
        }
      },

      checkAuth: async () => {
        const token = localStorage.getItem("access_token")
        if (!token) {
          set({ user: null, isAuthenticated: false })
          return
        }

        set({ isLoading: true })
        try {
          const user = await authApi.getMe()
          set({ user, isAuthenticated: true, isLoading: false })
        } catch {
          localStorage.removeItem("access_token")
          localStorage.removeItem("refresh_token")
          set({ user: null, isAuthenticated: false, isLoading: false })
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)
