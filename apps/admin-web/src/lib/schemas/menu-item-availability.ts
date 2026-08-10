import { z } from "zod"

export const menuItemAvailabilitySchema = z
  .object({
    branchId: z.string().min(1, "Choose a branch."),
    isAvailable: z.enum(["true", "false"]),
    effectiveFrom: z.string().min(1, "Choose a start date and time."),
    effectiveTo: z.string().optional(),
  })
  .refine(
    (value) => !value.effectiveTo || value.effectiveFrom < value.effectiveTo,
    { message: "Effective-from must be before effective-to.", path: ["effectiveTo"] }
  )

export type MenuItemAvailabilityFormValues = z.infer<typeof menuItemAvailabilitySchema>
