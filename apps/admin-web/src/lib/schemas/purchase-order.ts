import { z } from "zod"

export const createPurchaseOrderSchema = z.object({
  supplierId: z.string().min(1, "Choose a supplier."),
})

export type CreatePurchaseOrderFormValues = z.infer<typeof createPurchaseOrderSchema>

export const addPurchaseOrderItemSchema = z.object({
  inventoryItemId: z.string().min(1, "Choose an inventory item."),
  quantityOrdered: z.coerce.number().gt(0, "Quantity must be greater than zero."),
})

export type AddPurchaseOrderItemFormValues = z.infer<typeof addPurchaseOrderItemSchema>
