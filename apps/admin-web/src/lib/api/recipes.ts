import { apiClient } from "@/lib/api-client"
import type { Recipe, ReviseRecipeRequest } from "@/types/recipe"

export function getMenuItemRecipe(menuItemId: string) {
  return apiClient.get<Recipe>(`/api/v1/menu-items/${menuItemId}/recipe`)
}

export function reviseRecipe(menuItemId: string, body: ReviseRecipeRequest) {
  return apiClient.put<Recipe>(`/api/v1/menu-items/${menuItemId}/recipe`, body)
}
