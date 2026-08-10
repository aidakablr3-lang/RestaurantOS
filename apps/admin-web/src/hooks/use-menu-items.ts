import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createMenuItem,
  createMenuItemAvailability,
  createMenuItemBranchPrice,
  getMenuItem,
  listMenuItemAvailabilities,
  listMenuItemBranchPrices,
  listMenuItems,
  replaceMenuItemModifierGroups,
  updateMenuItem,
} from "@/lib/api/menu-items"
import type { CreateMenuItemAvailabilityRequest } from "@/types/menu-item-availability"
import type { CreateMenuItemBranchPriceRequest } from "@/types/menu-item-branch-price"
import type { ReplaceMenuItemModifierGroupsRequest } from "@/types/menu-item-modifier-groups"
import type {
  CreateMenuItemRequest,
  ListMenuItemsParams,
  UpdateMenuItemRequest,
} from "@/types/menu-item"

export const menuItemKeys = {
  all: ["menu-items"] as const,
  lists: (menuCategoryId: string) => [...menuItemKeys.all, "list", menuCategoryId] as const,
  list: (menuCategoryId: string, params: ListMenuItemsParams) =>
    [...menuItemKeys.lists(menuCategoryId), params] as const,
  details: (menuCategoryId: string) => [...menuItemKeys.all, "detail", menuCategoryId] as const,
  detail: (menuCategoryId: string, id: string) =>
    [...menuItemKeys.details(menuCategoryId), id] as const,
}

export function useMenuItems(
  menuCategoryId: string,
  params: ListMenuItemsParams,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: menuItemKeys.list(menuCategoryId, params),
    queryFn: () => listMenuItems(menuCategoryId, params),
    enabled: options?.enabled,
  })
}

export function useMenuItem(
  menuCategoryId: string,
  menuItemId: string | undefined,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: menuItemKeys.detail(menuCategoryId, menuItemId ?? ""),
    queryFn: () => getMenuItem(menuCategoryId, menuItemId as string),
    enabled: Boolean(menuItemId) && (options?.enabled ?? true),
  })
}

export function useCreateMenuItem(menuCategoryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateMenuItemRequest
      idempotencyKey: string
    }) => createMenuItem(menuCategoryId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: menuItemKeys.lists(menuCategoryId) })
    },
  })
}

export function useUpdateMenuItem(menuCategoryId: string, menuItemId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateMenuItemRequest) =>
      updateMenuItem(menuCategoryId, menuItemId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: menuItemKeys.detail(menuCategoryId, menuItemId) })
      queryClient.invalidateQueries({ queryKey: menuItemKeys.lists(menuCategoryId) })
    },
  })
}

// menuCategoryId is only needed here to invalidate this category's cached
// detail entry -- the mutation itself calls the flat, item-id-only route
// (see lib/api/menu-items.ts's own note on why that route has no
// menuCategoryId in its path).
export function useReplaceMenuItemModifierGroups(menuCategoryId: string, menuItemId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: ReplaceMenuItemModifierGroupsRequest
      idempotencyKey: string
    }) => replaceMenuItemModifierGroups(menuItemId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: menuItemKeys.detail(menuCategoryId, menuItemId) })
    },
  })
}

export const menuItemBranchPriceKeys = {
  list: (menuItemId: string) => ["menu-item-branch-prices", menuItemId] as const,
}

export function useMenuItemBranchPrices(menuItemId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: menuItemBranchPriceKeys.list(menuItemId),
    queryFn: () => listMenuItemBranchPrices(menuItemId),
    enabled: options?.enabled,
  })
}

export function useCreateMenuItemBranchPrice(menuItemId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateMenuItemBranchPriceRequest
      idempotencyKey: string
    }) => createMenuItemBranchPrice(menuItemId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: menuItemBranchPriceKeys.list(menuItemId) })
    },
  })
}

export const menuItemAvailabilityKeys = {
  list: (menuItemId: string) => ["menu-item-availabilities", menuItemId] as const,
}

export function useMenuItemAvailabilities(menuItemId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: menuItemAvailabilityKeys.list(menuItemId),
    queryFn: () => listMenuItemAvailabilities(menuItemId),
    enabled: options?.enabled,
  })
}

export function useCreateMenuItemAvailability(menuItemId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateMenuItemAvailabilityRequest
      idempotencyKey: string
    }) => createMenuItemAvailability(menuItemId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: menuItemAvailabilityKeys.list(menuItemId) })
    },
  })
}
