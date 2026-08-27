import { z } from "zod"

import { ISO_4217_CURRENCIES } from "@/lib/iso4217"

export const createTenantSchema = z.object({
  legalName: z
    .string()
    .min(1, "Legal name is required.")
    .max(255, "Legal name must be 255 characters or fewer."),
  displayName: z
    .string()
    .min(1, "Display name is required.")
    .max(255, "Display name must be 255 characters or fewer."),
  // A regex only checked *shape* ("3 uppercase letters"), which is how
  // "GST" (a tax, not a currency) got through -- this checks real
  // ISO 4217 membership instead, matching the dropdown's own options
  // and the API's own server-side validator so all three can't drift
  // apart again.
  defaultCurrencyCode: z
    .string()
    .refine((value) => value in ISO_4217_CURRENCIES, {
      message: "Select a valid ISO 4217 currency code.",
    }),
  ownerEmail: z
    .string()
    .min(1, "Owner email is required.")
    .email("Enter a valid email address."),
})

export type CreateTenantFormValues = z.infer<typeof createTenantSchema>

export const editTenantSchema = z.object({
  displayName: z
    .string()
    .min(1, "Display name is required.")
    .max(255, "Display name must be 255 characters or fewer."),
  metadata: z.string().refine(
    (value) => {
      if (value.trim() === "") return true
      try {
        const parsed = JSON.parse(value)
        return (
          typeof parsed === "object" &&
          parsed !== null &&
          !Array.isArray(parsed)
        )
      } catch {
        return false
      }
    },
    { message: "Metadata must be valid JSON representing an object." }
  ),
})

export type EditTenantFormValues = z.infer<typeof editTenantSchema>
