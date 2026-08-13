import { create } from "zustand"
import { persist } from "zustand/middleware"

import type { TokenPair } from "@/lib/api-types"

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  tenantId: string | null
  // The email the user typed on the login form -- stored client-side only
  // so the header can show "signed in as", never returned by any backend
  // endpoint (there is no GET /me/profile in this API yet).
  email: string | null
  setSession: (tokens: TokenPair, tenantId: string, email?: string) => void
  clearSession: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      tenantId: null,
      email: null,
      setSession: (tokens, tenantId, email) =>
        set({
          accessToken: tokens.accessToken,
          refreshToken: tokens.refreshToken,
          tenantId,
          email: email ?? get().email,
        }),
      clearSession: () =>
        set({ accessToken: null, refreshToken: null, tenantId: null, email: null }),
    }),
    { name: "restaurantos-admin-auth" }
  )
)
