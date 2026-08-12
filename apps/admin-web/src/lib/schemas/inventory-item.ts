import { z } from "zod"

export const createInventoryItemSchema = z.object({
  inventoryCategoryId: z.string().min(1, "Choose a category."),
  name: z.string().min(1, "Name is required."),
  unit: z.string().min(1, "Unit is required."),
  reorderPoint: z.coerce.number().optional(),
})

export type CreateInventoryItemFormValues = z.infer<typeof createInventoryItemSchema>

export const recordStockMovementSchema = z
  .object({
    movementType: z.enum(["adjustment", "waste", "transfer"]),
    quantityDelta: z.coerce.number().refine((v) => v !== 0, "Quantity cannot be zero."),
    reason: z.string().optional(),
  })
  .refine((values) => values.movementType !== "adjustment" || Boolean(values.reason?.trim()), {
    message: "A reason is required for adjustment movements.",
    path: ["reason"],
  })

export type RecordStockMovementFormValues = z.infer<typeof recordStockMovementSchema>
