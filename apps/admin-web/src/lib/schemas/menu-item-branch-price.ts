import { z } from "zod"

export const menuItemBranchPriceSchema = z
  .object({
    branchId: z.string().min(1, "Choose a branch."),
    priceAmount: z
      .string()
      .min(1, "Price is required.")
      .regex(/^\d+(\.\d{1,2})?$/, "Enter a valid amount, e.g. 8.99."),
    effectiveFrom: z.string().min(1, "Choose a start date and time."),
    effectiveTo: z.string().optional(),
  })
  .refine(
    (value) => !value.effectiveTo || value.effectiveFrom < value.effectiveTo,
    { message: "Effective-from must be before effective-to.", path: ["effectiveTo"] }
  )

export type MenuItemBranchPriceFormValues = z.infer<typeof menuItemBranchPriceSchema>
