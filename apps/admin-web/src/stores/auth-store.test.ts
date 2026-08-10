import { beforeEach, describe, expect, it } from "vitest"

import { useAuthStore } from "@/stores/auth-store"

const tokens = {
  accessToken: "access-1",
  refreshToken: "refresh-1",
  tokenType: "bearer",
  expiresIn: 900,
}

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      tenantId: null,
      email: null,
    })
  })

  it("stores tokens, tenantId, and email on setSession", () => {
    useAuthStore.getState().setSession(tokens, "tenant-1", "user@example.com")

    const state = useAuthStore.getState()
    expect(state.accessToken).toBe("access-1")
    expect(state.refreshToken).toBe("refresh-1")
    expect(state.tenantId).toBe("tenant-1")
    expect(state.email).toBe("user@example.com")
  })

  it("keeps the previously known email when a silent refresh omits it", () => {
    useAuthStore.getState().setSession(tokens, "tenant-1", "user@example.com")
    useAuthStore.getState().setSession(
      { ...tokens, accessToken: "access-2" },
      "tenant-1"
    )

    expect(useAuthStore.getState().email).toBe("user@example.com")
    expect(useAuthStore.getState().accessToken).toBe("access-2")
  })

  it("clears every field on clearSession", () => {
    useAuthStore.getState().setSession(tokens, "tenant-1", "user@example.com")

    useAuthStore.getState().clearSession()

    const state = useAuthStore.getState()
    expect(state.accessToken).toBeNull()
    expect(state.refreshToken).toBeNull()
    expect(state.tenantId).toBeNull()
    expect(state.email).toBeNull()
  })
})
