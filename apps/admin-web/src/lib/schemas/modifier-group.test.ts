import { describe, expect, it } from "vitest"

import { modifierGroupSchema } from "@/lib/schemas/modifier-group"

describe("modifierGroupSchema", () => {
  it("accepts a valid group", () => {
    const result = modifierGroupSchema.safeParse({ name: "Toppings", selectionType: "multiple" })
    expect(result.success).toBe(true)
  })

  it("rejects an empty name", () => {
    const result = modifierGroupSchema.safeParse({ name: "", selectionType: "single" })
    expect(result.success).toBe(false)
  })

  it("rejects a selection type outside single/multiple", () => {
    const result = modifierGroupSchema.safeParse({ name: "Toppings", selectionType: "any" })
    expect(result.success).toBe(false)
  })
})
