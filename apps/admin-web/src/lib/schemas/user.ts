import { z } from "zod"

export const createUserSchema = z.object({
  email: z.string().min(1, "Email is required.").email("Enter a valid email address."),
  phone: z.string().optional(),
})

export type CreateUserFormValues = z.infer<typeof createUserSchema>

export const assignRoleSchema = z.object({
  roleId: z.string().min(1, "Select a role."),
  branchId: z.string().optional(),
})

export type AssignRoleFormValues = z.infer<typeof assignRoleSchema>
