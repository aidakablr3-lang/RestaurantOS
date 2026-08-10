import { describe, expect, it } from "vitest"

import { modifierSchema } from "@/lib/schemas/modifier"

describe("modifierSchema", () => {
  it("accepts a positive price delta", () => {
    const result = modifierSchema.safeParse({ name: "Extra cheese", priceDelta: "1.50" })
    expect(result.success).toBe(true)
  })

  it("accepts a negative price delta (unlike menu item price, deltas may reduce price)", () => {
    const result = modifierSchema.safeParse({ name: "No cheese", priceDelta: "-0.50" })
    expect(result.success).toBe(true)
  })

  it("rejects an empty name", () => {
    const result = modifierSchema.safeParse({ name: "", priceDelta: "0.00" })
    expect(result.success).toBe(false)
  })

  it("rejects a non-decimal price delta", () => {
    const result = modifierSchema.safeParse({ name: "Extra cheese", priceDelta: "abc" })
    expect(result.success).toBe(false)
  })
})
