import { describe, expect, it } from "vitest"

import { suggestExistingCategory } from "./menu-import-helpers"

describe("suggestExistingCategory", () => {
  it("suggests a near-match that differs only slightly", () => {
    expect(suggestExistingCategory("Veg starter", ["Veg Starters", "Soups"])).toBe(
      "Veg Starters"
    )
  })

  it("returns null for an exact case-insensitive match -- nothing to suggest", () => {
    expect(suggestExistingCategory("SOUPS", ["Soups", "Veg Starters"])).toBeNull()
  })

  it("returns null when nothing is close enough", () => {
    expect(suggestExistingCategory("Main Course", ["Soups", "Veg Starters"])).toBeNull()
  })

  it("returns null for an empty name", () => {
    expect(suggestExistingCategory("", ["Soups"])).toBeNull()
  })

  it("returns null against an empty existing-categories list", () => {
    expect(suggestExistingCategory("Soups", [])).toBeNull()
  })

  it("picks the closest match when more than one is above threshold", () => {
    expect(
      suggestExistingCategory("Starter", ["Veg Starters", "Non-Veg Starters", "Starters"])
    ).toBe("Starters")
  })
})
