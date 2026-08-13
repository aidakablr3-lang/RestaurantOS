import { z } from "zod"

export const restaurantSchema = z.object({
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
})

export type RestaurantFormValues = z.infer<typeof restaurantSchema>
