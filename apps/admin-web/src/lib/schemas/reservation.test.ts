import { describe, expect, it } from "vitest"

import { reservationSchema } from "@/lib/schemas/reservation"

describe("reservationSchema", () => {
  it("accepts a valid reservation with no table", () => {
    const result = reservationSchema.safeParse({
      partySize: 4,
      requestedAt: "2026-01-01T19:00",
      tableId: "none",
    })
    expect(result.success).toBe(true)
  })

  it("rejects a zero or negative party size", () => {
    const result = reservationSchema.safeParse({
      partySize: 0,
      requestedAt: "2026-01-01T19:00",
    })
    expect(result.success).toBe(false)
  })

  it("rejects a missing requestedAt", () => {
    const result = reservationSchema.safeParse({ partySize: 2, requestedAt: "" })
    expect(result.success).toBe(false)
  })

  it("coerces a numeric string party size (HTML number inputs emit strings)", () => {
    const result = reservationSchema.safeParse({ partySize: "3", requestedAt: "2026-01-01T19:00" })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.partySize).toBe(3)
    }
  })
})
