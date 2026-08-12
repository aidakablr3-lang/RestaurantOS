import { z } from "zod"

export const createOrderSchema = z.object({
  orderSource: z.enum(["pos", "qr", "delivery", "takeaway"]),
  tableId: z.string().optional(),
})

export type CreateOrderFormValues = z.infer<typeof createOrderSchema>

export const addOrderItemSchema = z.object({
  menuItemId: z.string().min(1, "Choose a menu item."),
  quantity: z.coerce.number().int("Quantity must be a whole number.").gt(0, "Quantity must be greater than zero."),
})

export type AddOrderItemFormValues = z.infer<typeof addOrderItemSchema>
