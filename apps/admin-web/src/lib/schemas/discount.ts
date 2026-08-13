import { z } from "zod"

export const createDiscountSchema = z.object({
  name: z.string().min(1, "Name is required."),
  discountType: z.enum(["percentage", "fixed_amount"]),
  value: z.coerce.number().gt(0, "Value must be greater than zero."),
  requiresApproval: z.boolean(),
})

export type CreateDiscountFormValues = z.infer<typeof createDiscountSchema>
