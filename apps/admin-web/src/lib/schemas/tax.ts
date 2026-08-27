import { z } from "zod"

// The form collects a percent (9 for 9%) -- the API takes a fraction
// (0.09). A production incident was caused by a human doing that
// conversion by hand (dividing by 10 instead of 100) because the old
// form asked for the fraction directly with only a text hint; this is
// now the one place that conversion happens in code. 50 is an upper
// bound, not a real ceiling -- no restaurant tax rate is ever that
// high, so anything above it is almost certainly an un-converted
// fraction (e.g. "0.9" typed where "9" belonged), matching the
// backend's own CreateTaxUseCase/taxes.rate CHECK constraint bound.
export const createTaxSchema = z.object({
  name: z.string().min(1, "Name is required."),
  ratePercent: z.coerce
    .number()
    .gte(0, "Rate must be at least 0%.")
    .lte(50, "Rate must be 50% or less. If you meant to enter a fraction (e.g. 0.09), enter 9 instead."),
})

export type CreateTaxFormValues = z.infer<typeof createTaxSchema>

/** 9 -> "0.0900". Rounds to 4 decimal places, matching taxes.rate's
 * NUMERIC(6,4) column -- the same precision the backend stores. */
export function percentToFractionString(percent: number): string {
  return (percent / 100).toFixed(4)
}

/** "0.0900" -> "9%". For displaying an existing stored rate back to a
 * human in the unit they think in, not the fraction the API/DB use. */
export function fractionToPercentLabel(rate: string): string {
  const percent = Number(rate) * 100
  return `${Number(percent.toFixed(4))}%`
}
