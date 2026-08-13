import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { QRCodeStatusBadge } from "@/components/qr-code-status-badge"

describe("QRCodeStatusBadge", () => {
  it("labels an active code as Active", () => {
    render(<QRCodeStatusBadge status="active" />)
    expect(screen.getByText("Active")).toBeInTheDocument()
  })

  it("labels a revoked code as Revoked", () => {
    render(<QRCodeStatusBadge status="revoked" />)
    expect(screen.getByText("Revoked")).toBeInTheDocument()
  })
})
