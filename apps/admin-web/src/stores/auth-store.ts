import { create } from "zustand"
import { persist } from "zustand/middleware"

import type { TokenPair } from "@/lib/api-types"

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  tenantId: string | null
  setSession: (tokens: TokenPair, tenantId: string) => void
  clearSession: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      tenantId: null,
      setSession: (tokens, tenantId) =>
        set({
          accessToken: tokens.accessToken,
          refreshToken: tokens.refreshToken,
          tenantId,
        }),
      clearSession: () =>
        set({ accessToken: null, refreshToken: null, tenantId: null }),
    }),
    { name: "restaurantos-admin-auth" }
  )
)
