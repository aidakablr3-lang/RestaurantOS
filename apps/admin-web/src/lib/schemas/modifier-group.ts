import { z } from "zod"

export const modifierGroupSchema = z.object({
  name: z
    .string()
    .min(1, "Group name is required.")
    .max(255, "Name must be 255 characters or fewer."),
  selectionType: z.enum(["single", "multiple"]),
})

export type ModifierGroupFormValues = z.infer<typeof modifierGroupSchema>
