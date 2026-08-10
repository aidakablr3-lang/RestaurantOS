import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createBranch,
  createRestaurant,
  discontinueRestaurant,
  getRestaurant,
  listRestaurants,
  updateRestaurant,
} from "@/lib/api/restaurants"
import type {
  CreateRestaurantRequest,
  ListRestaurantsParams,
  UpdateRestaurantRequest,
} from "@/types/restaurant"
import type { CreateBranchRequest } from "@/types/branch"

export const restaurantKeys = {
  all: ["restaurants"] as const,
  lists: () => [...restaurantKeys.all, "list"] as const,
  list: (params: ListRestaurantsParams) => [...restaurantKeys.lists(), params] as const,
  details: () => [...restaurantKeys.all, "detail"] as const,
  detail: (id: string) => [...restaurantKeys.details(), id] as const,
}

export function useRestaurants(params: ListRestaurantsParams, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: restaurantKeys.list(params),
    queryFn: () => listRestaurants(params),
    enabled: options?.enabled,
  })
}

export function useRestaurant(restaurantId: string | undefined) {
  return useQuery({
    queryKey: restaurantKeys.detail(restaurantId ?? ""),
    queryFn: () => getRestaurant(restaurantId as string),
    enabled: Boolean(restaurantId),
  })
}

export function useCreateRestaurant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateRestaurantRequest
      idempotencyKey: string
    }) => createRestaurant(body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.lists() })
    },
  })
}

export function useUpdateRestaurant(restaurantId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateRestaurantRequest) => updateRestaurant(restaurantId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.detail(restaurantId) })
      queryClient.invalidateQueries({ queryKey: restaurantKeys.lists() })
    },
  })
}

export function useDiscontinueRestaurant(restaurantId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (idempotencyKey: string) =>
      discontinueRestaurant(restaurantId, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.detail(restaurantId) })
      queryClient.invalidateQueries({ queryKey: restaurantKeys.lists() })
    },
  })
}

export function useCreateBranch(restaurantId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: CreateBranchRequest
      idempotencyKey: string
    }) => createBranch(restaurantId, body, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["branches"] })
    },
  })
}
