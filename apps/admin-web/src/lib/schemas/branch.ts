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
  // 2-digit state code + 10-char PAN (5 letters, 4 digits, 1 letter) +
  // 1 entity-count char + literal 'Z' + 1 checksum char = 15,
  // mirroring the backend's own format check (format only, no
  // checksum verification).
  gstin: z
    .string()
    .optional()
    .refine(
      (value) => !value || /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(value),
      {
        message:
          "GSTIN must be 15 characters: 2-digit state code, 10-character PAN, 1 entity-count character, 'Z', 1 checksum character.",
      }
    ),
  // An invoice number series belongs to a GST registration -- two
  // branches sharing one GSTIN must not share a prefix, but two
  // branches with different (or no) GSTINs may. Leave blank to keep
  // the auto-generated default from when the branch was created.
  invoicePrefix: z
    .string()
    .optional()
    .refine((value) => !value || /^[A-Z0-9]{2,10}$/.test(value), {
      message: "Invoice prefix must be 2-10 uppercase letters/digits.",
    }),
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
