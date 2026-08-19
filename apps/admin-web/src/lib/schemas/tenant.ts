import { z } from "zod"

export const createTenantSchema = z.object({
  legalName: z
    .string()
    .min(1, "Legal name is required.")
    .max(255, "Legal name must be 255 characters or fewer."),
  displayName: z
    .string()
    .min(1, "Display name is required.")
    .max(255, "Display name must be 255 characters or fewer."),
  defaultCurrencyCode: z
    .string()
    .regex(/^[A-Z]{3}$/, "Enter a 3-letter ISO 4217 currency code (e.g. USD)."),
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
