import { z } from "zod"

export const createTaxSchema = z.object({
  name: z.string().min(1, "Name is required."),
  rate: z.coerce
    .number()
    .gte(0, "Rate must be at least 0.")
    .lte(1, "Rate must be at most 1 (e.g. 0.10 for 10%)."),
})

export type CreateTaxFormValues = z.infer<typeof createTaxSchema>
