import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { TableStatusBadge } from "@/components/table-status-badge"
import type { TableStatus } from "@/types/table"

describe("TableStatusBadge", () => {
  it.each<[TableStatus, string]>([
    ["available", "Available"],
    ["occupied", "Occupied"],
    ["reserved", "Reserved"],
    ["cleaning", "Cleaning"],
  ])("labels %s as %s", (status, label) => {
    render(<TableStatusBadge status={status} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})
