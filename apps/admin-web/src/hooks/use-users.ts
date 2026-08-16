import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { createUser, listUsers } from "@/lib/api/users"
import type { CreateUserRequest, ListUsersParams } from "@/types/user"

export const userKeys = {
  all: ["users"] as const,
  lists: () => [...userKeys.all, "list"] as const,
  list: (params: ListUsersParams) => [...userKeys.lists(), params] as const,
}

export function useUsers(params: ListUsersParams, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: userKeys.list(params),
    queryFn: () => listUsers(params),
    enabled: options?.enabled,
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateUserRequest) => createUser(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.lists() })
    },
  })
}
