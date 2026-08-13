import { describe, expect, it } from "vitest"

import { menuItemBranchPriceSchema } from "@/lib/schemas/menu-item-branch-price"

describe("menuItemBranchPriceSchema", () => {
  it("accepts a valid override with no end date", () => {
    const result = menuItemBranchPriceSchema.safeParse({
      branchId: "01BRANCHID0000000000000000",
      priceAmount: "12.50",
      effectiveFrom: "2026-01-01T00:00",
    })
    expect(result.success).toBe(true)
  })

  it("rejects when effectiveTo is before effectiveFrom", () => {
    const result = menuItemBranchPriceSchema.safeParse({
      branchId: "01BRANCHID0000000000000000",
      priceAmount: "12.50",
      effectiveFrom: "2026-01-02T00:00",
      effectiveTo: "2026-01-01T00:00",
    })
    expect(result.success).toBe(false)
  })

  it("accepts when effectiveTo is after effectiveFrom", () => {
    const result = menuItemBranchPriceSchema.safeParse({
      branchId: "01BRANCHID0000000000000000",
      priceAmount: "12.50",
      effectiveFrom: "2026-01-01T00:00",
      effectiveTo: "2026-01-02T00:00",
    })
    expect(result.success).toBe(true)
  })

  it("rejects a missing branch", () => {
    const result = menuItemBranchPriceSchema.safeParse({
      branchId: "",
      priceAmount: "12.50",
      effectiveFrom: "2026-01-01T00:00",
    })
    expect(result.success).toBe(false)
  })
})
