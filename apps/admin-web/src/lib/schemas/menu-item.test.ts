import { describe, expect, it } from "vitest"

import { menuItemSchema } from "@/lib/schemas/menu-item"

describe("menuItemSchema", () => {
  it("accepts a valid menu item", () => {
    const result = menuItemSchema.safeParse({
      name: "Spring Rolls",
      priceAmount: "8.99",
      currencyCode: "usd",
      isAvailable: true,
      displayOrder: 0,
    })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.currencyCode).toBe("USD")
    }
  })

  it("rejects an empty name", () => {
    const result = menuItemSchema.safeParse({
      name: "",
      priceAmount: "8.99",
      currencyCode: "USD",
      isAvailable: true,
      displayOrder: 0,
    })
    expect(result.success).toBe(false)
  })

  it("rejects a price that isn't a valid decimal string", () => {
    const result = menuItemSchema.safeParse({
      name: "Spring Rolls",
      priceAmount: "not-a-number",
      currencyCode: "USD",
      isAvailable: true,
      displayOrder: 0,
    })
    expect(result.success).toBe(false)
  })

  it("rejects a currency code that isn't exactly 3 letters", () => {
    const result = menuItemSchema.safeParse({
      name: "Spring Rolls",
      priceAmount: "8.99",
      currencyCode: "US",
      isAvailable: true,
      displayOrder: 0,
    })
    expect(result.success).toBe(false)
  })

  it("accepts a whole-number price with no decimal part", () => {
    const result = menuItemSchema.safeParse({
      name: "Spring Rolls",
      priceAmount: "9",
      currencyCode: "USD",
      isAvailable: true,
      displayOrder: 0,
    })
    expect(result.success).toBe(true)
  })
})
