import { describe, expect, it } from "vitest"

import { menuCategorySchema } from "@/lib/schemas/menu-category"

describe("menuCategorySchema", () => {
  it("accepts a valid name with the default display order", () => {
    const result = menuCategorySchema.safeParse({ name: "Appetizers", displayOrder: 0 })
    expect(result.success).toBe(true)
  })

  it("rejects an empty name", () => {
    const result = menuCategorySchema.safeParse({ name: "", displayOrder: 0 })
    expect(result.success).toBe(false)
  })

  it("rejects a negative display order", () => {
    const result = menuCategorySchema.safeParse({ name: "Appetizers", displayOrder: -1 })
    expect(result.success).toBe(false)
  })
})
