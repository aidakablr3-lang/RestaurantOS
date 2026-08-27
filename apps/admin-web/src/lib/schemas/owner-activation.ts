import { z } from "zod"

export const activateOwnerSchema = z
  .object({
    newPassword: z.string().min(8, "Password must be at least 8 characters."),
    confirmPassword: z.string().min(8, "Password must be at least 8 characters."),
  })
  .refine((values) => values.newPassword === values.confirmPassword, {
    message: "Passwords don't match.",
    path: ["confirmPassword"],
  })

export type ActivateOwnerFormValues = z.infer<typeof activateOwnerSchema>
