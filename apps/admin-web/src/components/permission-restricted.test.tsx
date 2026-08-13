import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { PermissionRestricted } from "@/components/permission-restricted"

describe("PermissionRestricted", () => {
  it("names the restricted resource in its description", () => {
    render(<PermissionRestricted resource="branches" />)

    expect(screen.getByText("You don't have access")).toBeInTheDocument()
    expect(screen.getByText(/permission to view branches/)).toBeInTheDocument()
  })

  it("falls back to a generic description when no resource is given", () => {
    render(<PermissionRestricted />)

    expect(screen.getByText(/permission to view this page/)).toBeInTheDocument()
  })
})
