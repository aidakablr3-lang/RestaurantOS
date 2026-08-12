import { z } from "zod"

export const createInventoryCategorySchema = z.object({
  name: z.string().min(1, "Name is required."),
})

export type CreateInventoryCategoryFormValues = z.infer<typeof createInventoryCategorySchema>
