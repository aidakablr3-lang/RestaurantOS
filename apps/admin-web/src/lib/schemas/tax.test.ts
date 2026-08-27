import { describe, expect, it } from "vitest"

import {
  createTaxSchema,
  fractionToPercentLabel,
  percentToFractionString,
} from "@/lib/schemas/tax"

describe("percentToFractionString", () => {
  it("converts 9% and 9% (CGST + SGST) to the paisa", () => {
    // Regression test for a production incident: 9% was stored as the
    // fraction 0.9 instead of 0.09, overcharging every bill 10x. This
    // is the one place percent -> fraction conversion happens now.
    expect(percentToFractionString(9)).toBe("0.0900")
  })

  it("rounds to 4 decimal places, matching taxes.rate's NUMERIC(6,4) column", () => {
    expect(percentToFractionString(18.5)).toBe("0.1850")
    expect(percentToFractionString(2.5)).toBe("0.0250")
  })

  it("never divides by 10 instead of 100", () => {
    expect(percentToFractionString(9)).not.toBe("0.9")
    expect(percentToFractionString(9)).not.toBe("0.9000")
  })
})

describe("fractionToPercentLabel", () => {
  it("shows a stored fraction back to a human as a percent", () => {
    expect(fractionToPercentLabel("0.0900")).toBe("9%")
    expect(fractionToPercentLabel("0.1000")).toBe("10%")
  })
})

describe("createTaxSchema", () => {
  it("accepts 9% and 50%", () => {
    expect(createTaxSchema.safeParse({ name: "CGST", ratePercent: 9 }).success).toBe(true)
    expect(createTaxSchema.safeParse({ name: "Excise", ratePercent: 50 }).success).toBe(true)
  })

  it("rejects anything above 50%", () => {
    // The exact production incident: a fraction (0.9, meant to be
    // stored as the rate) typed into a percent field would be 90%.
    const result = createTaxSchema.safeParse({ name: "CGST", ratePercent: 90 })
    expect(result.success).toBe(false)
  })

  it("rejects a negative rate", () => {
    expect(createTaxSchema.safeParse({ name: "CGST", ratePercent: -1 }).success).toBe(false)
  })
})
