import { describe, expect, it } from "vitest"

import { restaurantSchema } from "@/lib/schemas/restaurant"

describe("restaurantSchema", () => {
  it("accepts a valid restaurant", () => {
    const result = restaurantSchema.safeParse({
      legalName: "Acme Restaurants LLC",
      displayName: "Acme Kitchen",
      defaultCurrencyCode: "USD",
    })
    expect(result.success).toBe(true)
  })

  it("rejects an empty legal name", () => {
    const result = restaurantSchema.safeParse({
      legalName: "",
      displayName: "Acme Kitchen",
      defaultCurrencyCode: "USD",
    })
    expect(result.success).toBe(false)
  })

  it("rejects a currency code that isn't 3 uppercase letters", () => {
    const result = restaurantSchema.safeParse({
      legalName: "Acme",
      displayName: "Acme",
      defaultCurrencyCode: "us",
    })
    expect(result.success).toBe(false)
  })
})
