import { z } from "zod"

// price_amount travels as a Decimal-precision string on the wire (see
// types/menu-item.ts) -- validated as a non-negative decimal string
// rather than coerced to a JS number, to avoid the float-precision loss
// the backend's own Decimal type exists to prevent.
const moneyString = z
  .string()
  .min(1, "Price is required.")
  .regex(/^\d+(\.\d{1,2})?$/, "Enter a valid amount, e.g. 8.99.")

export const menuItemSchema = z.object({
  name: z
    .string()
    .min(1, "Item name is required.")
    .max(255, "Name must be 255 characters or fewer."),
  priceAmount: moneyString,
  currencyCode: z
    .string()
    .length(3, "Enter a 3-letter ISO 4217 currency code (e.g. USD).")
    .transform((value) => value.toUpperCase()),
  isAvailable: z.boolean(),
  displayOrder: z.coerce
    .number()
    .int("Display order must be a whole number.")
    .min(0, "Display order cannot be negative."),
  station: z.enum(["kitchen", "bar"]),
})

export type MenuItemFormValues = z.infer<typeof menuItemSchema>
