import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { AuthGuard } from "@/components/auth-guard"
import { useAuthStore } from "@/stores/auth-store"

const replace = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}))

describe("AuthGuard", () => {
  beforeEach(() => {
    replace.mockClear()
    useAuthStore.setState({ accessToken: null, refreshToken: null, tenantId: null, email: null })
  })

  it("renders children once hydrated with a valid session", async () => {
    useAuthStore.setState({ accessToken: "access-1" })

    render(
      <AuthGuard>
        <div>Protected content</div>
      </AuthGuard>
    )

    await waitFor(() => expect(screen.getByText("Protected content")).toBeInTheDocument())
    expect(replace).not.toHaveBeenCalled()
  })

  it("redirects to /login once hydrated with no session, without rendering children", async () => {
    render(
      <AuthGuard>
        <div>Protected content</div>
      </AuthGuard>
    )

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"))
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument()
  })
})
