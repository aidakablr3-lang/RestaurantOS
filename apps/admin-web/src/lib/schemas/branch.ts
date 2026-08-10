import { z } from "zod"

export const branchSchema = z.object({
  name: z
    .string()
    .min(1, "Branch name is required.")
    .max(255, "Branch name must be 255 characters or fewer."),
  line1: z.string().max(255).optional(),
  city: z.string().max(255).optional(),
  countryCode: z
    .string()
    .max(2)
    .optional()
    .refine((value) => !value || /^[A-Z]{2}$/.test(value), {
      message: "Enter a 2-letter ISO 3166-1 country code (e.g. US).",
    }),
  postalCode: z.string().max(32).optional(),
})

export type BranchFormValues = z.infer<typeof branchSchema>

const DAY_LABELS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const

export function dayLabel(dayOfWeek: number): string {
  return DAY_LABELS[dayOfWeek] ?? `Day ${dayOfWeek}`
}
