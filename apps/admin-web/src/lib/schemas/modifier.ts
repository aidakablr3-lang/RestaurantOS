import { z } from "zod"

export const modifierSchema = z.object({
  name: z
    .string()
    .min(1, "Modifier name is required.")
    .max(255, "Name must be 255 characters or fewer."),
  // Unlike menu item price_amount, the backend's own price_delta has no
  // ge=0 constraint -- a modifier may legitimately reduce price (e.g. a
  // "no cheese" option), so a leading minus is allowed here.
  priceDelta: z
    .string()
    .min(1, "Price delta is required.")
    .regex(/^-?\d+(\.\d{1,2})?$/, "Enter a valid amount, e.g. 1.50 or -0.50."),
})

export type ModifierFormValues = z.infer<typeof modifierSchema>
