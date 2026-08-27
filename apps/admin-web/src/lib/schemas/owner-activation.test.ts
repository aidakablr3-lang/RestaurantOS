import { describe, expect, it } from "vitest"

import { activateOwnerSchema } from "@/lib/schemas/owner-activation"

describe("activateOwnerSchema", () => {
  it("accepts matching passwords of at least 8 characters", () => {
    const result = activateOwnerSchema.safeParse({
      newPassword: "correct horse",
      confirmPassword: "correct horse",
    })
    expect(result.success).toBe(true)
  })

  it("rejects mismatched passwords", () => {
    const result = activateOwnerSchema.safeParse({
      newPassword: "correct horse",
      confirmPassword: "different horse",
    })
    expect(result.success).toBe(false)
  })

  it("rejects a password shorter than 8 characters", () => {
    const result = activateOwnerSchema.safeParse({
      newPassword: "short1",
      confirmPassword: "short1",
    })
    expect(result.success).toBe(false)
  })
})
