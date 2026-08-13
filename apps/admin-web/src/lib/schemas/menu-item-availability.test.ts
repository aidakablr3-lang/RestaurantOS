import { describe, expect, it } from "vitest"

import { menuItemAvailabilitySchema } from "@/lib/schemas/menu-item-availability"

describe("menuItemAvailabilitySchema", () => {
  it("accepts a valid override", () => {
    const result = menuItemAvailabilitySchema.safeParse({
      branchId: "01BRANCHID0000000000000000",
      isAvailable: "false",
      effectiveFrom: "2026-01-01T00:00",
    })
    expect(result.success).toBe(true)
  })

  it("rejects when effectiveTo is before effectiveFrom", () => {
    const result = menuItemAvailabilitySchema.safeParse({
      branchId: "01BRANCHID0000000000000000",
      isAvailable: "true",
      effectiveFrom: "2026-01-02T00:00",
      effectiveTo: "2026-01-01T00:00",
    })
    expect(result.success).toBe(false)
  })
})
