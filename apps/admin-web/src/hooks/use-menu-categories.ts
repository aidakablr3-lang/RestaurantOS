import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createMenuCategory,
  getMenuCategory,
  listMenuCategories,
  updateMenuCategory,
} from "@/lib/api/menu-categories"
import type {
  CreateMenuCategoryRequest,
  ListMenuCategoriesParams,
  UpdateMenuCategoryRequest,
} from "@/types/menu-category"

export const menuCategoryKeys = {
  all: ["menu-categories"] as const,
  lists: (restaurantId: string) => [...menuCategoryKeys.all, "list", restaurantId] as const,
  list: (restaurantId: string, params: ListMenuCategoriesParams) =>
    [...menuCategoryKeys.lists(restaurantId), params] as const,
  details: (restaurantId: string) => [...menuCategoryKeys.all, "detail", restaurantId] as const,
  detail: (restaurantId: string, id: string) =>
    [...menuCategoryKeys.details(restaurantId), id] as const,
}

export function useMenuCategories(
  restaurantId: string,
  params: ListMenuCategoriesParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: menuCategoryKeys.list(restaurantId, params),
    queryFn: () => listMenuCategories(restaurantId, params),
    enabled: options?.enabled,
  })
}

export function useMenuCategory(
  restaurantId: string,
  menuCategoryId: string | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: menuCategoryKeys.detail(restaurantId, menuCategoryId ?? ""),
    queryFn: () => getMenuCategory(restaurantId, menuCategoryId as string),
    enabled: Boolean(menuCategoryId) && (options?.enabled ?? true),
  })
}

export function useCreateMenuCategory(restaurantId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateMenuCategoryRequest
      idempotencyKey: string
    }) => createMenuCategory(restaurantId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: menuCategoryKeys.lists(restaurantId) })
    },
  })
}

export function useUpdateMenuCategory(restaurantId: string, menuCategoryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateMenuCategoryRequest) =>
      updateMenuCategory(restaurantId, menuCategoryId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: menuCategoryKeys.detail(restaurantId, menuCategoryId),
      })
      queryClient.invalidateQueries({ queryKey: menuCategoryKeys.lists(restaurantId) })
    },
  })
}
