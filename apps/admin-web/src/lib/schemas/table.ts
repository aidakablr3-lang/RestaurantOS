import { z } from "zod"

export const tableSchema = z.object({
  tableZoneId: z.string().min(1, "Choose a dining area."),
  tableNumber: z
    .string()
    .min(1, "Table number is required.")
    .max(255, "Table number must be 255 characters or fewer."),
  capacity: z.coerce
    .number()
    .int("Capacity must be a whole number.")
    .gt(0, "Capacity must be greater than zero."),
})

export type TableFormValues = z.infer<typeof tableSchema>
