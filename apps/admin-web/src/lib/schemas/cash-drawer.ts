import { z } from "zod"

export const openCashDrawerSchema = z.object({
  openingFloatAmount: z.coerce.number().gte(0, "Opening float cannot be negative."),
  terminalId: z.string().optional(),
})

export type OpenCashDrawerFormValues = z.infer<typeof openCashDrawerSchema>

export const closeCashDrawerSchema = z.object({
  closingCountedAmount: z.coerce.number().gte(0, "Counted amount cannot be negative."),
})

export type CloseCashDrawerFormValues = z.infer<typeof closeCashDrawerSchema>
