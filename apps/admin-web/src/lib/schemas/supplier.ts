import { z } from "zod"

export const createSupplierSchema = z.object({
  name: z.string().min(1, "Name is required."),
})

export type CreateSupplierFormValues = z.infer<typeof createSupplierSchema>

export const updateSupplierSchema = z.object({
  name: z.string().min(1, "Name is required."),
  status: z.enum(["active", "inactive"]),
})

export type UpdateSupplierFormValues = z.infer<typeof updateSupplierSchema>
