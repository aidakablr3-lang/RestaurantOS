import { z } from "zod"

export const applyBillAdjustmentSchema = z.object({
  adjustmentType: z.enum(["discount", "service_charge", "tip", "comp", "write_off"]),
  amount: z.coerce.number().gt(0, "Amount must be greater than zero."),
  reason: z.string().optional(),
})

export type ApplyBillAdjustmentFormValues = z.infer<typeof applyBillAdjustmentSchema>

export const recordPaymentSchema = z.object({
  tenderType: z.enum(["cash", "card", "wallet"]),
  amount: z.coerce.number().gt(0, "Amount must be greater than zero."),
  tipAmount: z.coerce.number().gte(0, "Tip cannot be negative."),
})

export type RecordPaymentFormValues = z.infer<typeof recordPaymentSchema>

export const requestRefundSchema = z.object({
  amount: z.coerce.number().gt(0, "Amount must be greater than zero."),
})

export type RequestRefundFormValues = z.infer<typeof requestRefundSchema>
