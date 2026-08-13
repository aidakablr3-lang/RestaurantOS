import { z } from "zod"

export const menuCategorySchema = z.object({
  name: z
    .string()
    .min(1, "Category name is required.")
    .max(255, "Name must be 255 characters or fewer."),
  displayOrder: z.coerce
    .number()
    .int("Display order must be a whole number.")
    .min(0, "Display order cannot be negative."),
})

export type MenuCategoryFormValues = z.infer<typeof menuCategorySchema>
