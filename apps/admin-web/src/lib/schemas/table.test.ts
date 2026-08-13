import { describe, expect, it } from "vitest"

import { tableSchema } from "@/lib/schemas/table"

describe("tableSchema", () => {
  it("accepts a valid table", () => {
    const result = tableSchema.safeParse({
      tableZoneId: "01ZONEID000000000000000000",
      tableNumber: "12",
      capacity: 4,
    })
    expect(result.success).toBe(true)
  })

  it("rejects a missing dining area", () => {
    const result = tableSchema.safeParse({ tableZoneId: "", tableNumber: "12", capacity: 4 })
    expect(result.success).toBe(false)
  })

  it("rejects an empty table number", () => {
    const result = tableSchema.safeParse({
      tableZoneId: "01ZONEID000000000000000000",
      tableNumber: "",
      capacity: 4,
    })
    expect(result.success).toBe(false)
  })

  it("rejects a zero or negative capacity", () => {
    const result = tableSchema.safeParse({
      tableZoneId: "01ZONEID000000000000000000",
      tableNumber: "12",
      capacity: 0,
    })
    expect(result.success).toBe(false)
  })

  it("rejects a non-integer capacity", () => {
    const result = tableSchema.safeParse({
      tableZoneId: "01ZONEID000000000000000000",
      tableNumber: "12",
      capacity: 2.5,
    })
    expect(result.success).toBe(false)
  })
})
