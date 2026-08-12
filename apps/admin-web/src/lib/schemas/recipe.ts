import { z } from "zod"

export const recipeIngredientRowSchema = z.object({
  inventoryItemId: z.string().min(1, "Choose an inventory item."),
  quantity: z.coerce.number().gt(0, "Quantity must be greater than zero."),
  unit: z.string().min(1, "Unit is required."),
})

export const reviseRecipeSchema = z.object({
  name: z.string().min(1, "Name is required."),
  ingredients: z.array(recipeIngredientRowSchema),
})

export type ReviseRecipeFormValues = z.infer<typeof reviseRecipeSchema>
