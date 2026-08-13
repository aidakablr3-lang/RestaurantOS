import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { getMenuItemRecipe, reviseRecipe } from "@/lib/api/recipes"
import type { ReviseRecipeRequest } from "@/types/recipe"

export const recipeKeys = {
  all: ["recipes"] as const,
  detail: (menuItemId: string) => [...recipeKeys.all, "detail", menuItemId] as const,
}

export function useMenuItemRecipe(menuItemId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: recipeKeys.detail(menuItemId),
    queryFn: () => getMenuItemRecipe(menuItemId),
    enabled: options?.enabled,
    // A menu item with no recipe yet is a routine 404 (RECIPE_NOT_FOUND),
    // not a transient failure -- retrying it would just repeat the same
    // 404 three more times before giving up anyway.
    retry: false,
  })
}

export function useReviseRecipe(menuItemId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ReviseRecipeRequest) => reviseRecipe(menuItemId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: recipeKeys.detail(menuItemId) })
    },
  })
}
