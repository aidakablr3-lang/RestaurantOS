import { useMutation, useQueryClient } from "@tanstack/react-query"

import { menuCategoryKeys } from "@/hooks/use-menu-categories"
import { commitMenuImport, extractMenuImport } from "@/lib/api/menu-imports"
import type { MenuImportCommitRow } from "@/types/menu-import"

export function useExtractMenuImport(restaurantId: string) {
  return useMutation({
    mutationFn: (files: File[]) => extractMenuImport(restaurantId, files),
  })
}

export function useCommitMenuImport(restaurantId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      rows,
      idempotencyKey,
    }: {
      rows: MenuImportCommitRow[]
      idempotencyKey: string
    }) => commitMenuImport(restaurantId, rows, idempotencyKey),
    onSuccess: () => {
      // New categories may have been created; individual category item
      // lists refetch naturally when their own pages are next visited.
      queryClient.invalidateQueries({ queryKey: menuCategoryKeys.lists(restaurantId) })
    },
  })
}
