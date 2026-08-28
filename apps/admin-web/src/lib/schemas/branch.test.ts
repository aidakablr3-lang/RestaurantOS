import { describe, expect, it } from "vitest"

import { branchSchema, dayLabel } from "@/lib/schemas/branch"

describe("branchSchema", () => {
  it("accepts a name with no address", () => {
    const result = branchSchema.safeParse({ name: "Downtown" })
    expect(result.success).toBe(true)
  })

  it("rejects an empty name", () => {
    const result = branchSchema.safeParse({ name: "" })
    expect(result.success).toBe(false)
  })

  it("rejects a country code that isn't 2 uppercase letters", () => {
    const result = branchSchema.safeParse({ name: "Downtown", countryCode: "usa" })
    expect(result.success).toBe(false)
  })

  it("accepts a valid 2-letter country code", () => {
    const result = branchSchema.safeParse({ name: "Downtown", countryCode: "US" })
    expect(result.success).toBe(true)
  })

  it("accepts a branch with no gstin", () => {
    const result = branchSchema.safeParse({ name: "Downtown" })
    expect(result.success).toBe(true)
  })

  it("accepts a valid gstin", () => {
    const result = branchSchema.safeParse({ name: "Downtown", gstin: "29ABCDE1234F1Z5" })
    expect(result.success).toBe(true)
  })

  it("rejects a gstin that's one character short", () => {
    const result = branchSchema.safeParse({ name: "Downtown", gstin: "29ABCDE1234F1Z" })
    expect(result.success).toBe(false)
  })

  it("rejects a lowercase gstin", () => {
    const result = branchSchema.safeParse({ name: "Downtown", gstin: "29abcde1234f1z5" })
    expect(result.success).toBe(false)
  })
})

describe("dayLabel", () => {
  it("maps 0-6 to weekday names starting on Sunday", () => {
    expect(dayLabel(0)).toBe("Sunday")
    expect(dayLabel(6)).toBe("Saturday")
  })
})
