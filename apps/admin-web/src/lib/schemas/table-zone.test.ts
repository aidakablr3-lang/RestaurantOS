import { describe, expect, it } from "vitest"

import { tableZoneSchema } from "@/lib/schemas/table-zone"

describe("tableZoneSchema", () => {
  it("accepts a valid name with the default display order", () => {
    const result = tableZoneSchema.safeParse({ name: "Patio", displayOrder: 0 })
    expect(result.success).toBe(true)
  })

  it("rejects an empty name", () => {
    const result = tableZoneSchema.safeParse({ name: "", displayOrder: 0 })
    expect(result.success).toBe(false)
  })

  it("rejects a negative display order", () => {
    const result = tableZoneSchema.safeParse({ name: "Patio", displayOrder: -1 })
    expect(result.success).toBe(false)
  })

  it("coerces a numeric string display order (HTML number inputs emit strings)", () => {
    const result = tableZoneSchema.safeParse({ name: "Patio", displayOrder: "3" })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.displayOrder).toBe(3)
    }
  })
})
