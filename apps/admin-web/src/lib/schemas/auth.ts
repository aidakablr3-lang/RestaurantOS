import { z } from "zod"

export const loginSchema = z.object({
  tenantId: z
    .string()
    .length(26, "Tenant ID must be exactly 26 characters (ULID)."),
  email: z.string().min(3).max(320).email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
})

export type LoginFormValues = z.infer<typeof loginSchema>
