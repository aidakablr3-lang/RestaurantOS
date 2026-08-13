/**
 * Mirrors modules/operations/presentation/api/v1/recipe_router.py's
 * RecipeResponseSchema / RecipeIngredientResponseSchema /
 * ReviseRecipeRequestSchema. Field names are camelCase on the wire;
 * quantity fields are decimal strings.
 */

export interface RecipeIngredient {
  id: string
  recipeId: string
  inventoryItemId: string
  quantity: string
  unit: string
  createdAt: string
}

export interface Recipe {
  id: string
  tenantId: string
  name: string
  version: number
  createdAt: string
  supersededById: string | null
  ingredients: RecipeIngredient[]
}

export interface ReviseRecipeIngredientRequest {
  inventoryItemId: string
  quantity: string
  unit: string
}

export interface ReviseRecipeRequest {
  name: string
  ingredients: ReviseRecipeIngredientRequest[]
}
