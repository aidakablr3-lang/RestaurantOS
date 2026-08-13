import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { createSupplier, listSuppliers, updateSupplier } from "@/lib/api/suppliers"
import type { CreateSupplierRequest, ListSuppliersParams, UpdateSupplierRequest } from "@/types/supplier"

export const supplierKeys = {
  all: ["suppliers"] as const,
  lists: () => [...supplierKeys.all, "list"] as const,
  list: (params: ListSuppliersParams) => [...supplierKeys.lists(), params] as const,
}

export function useSuppliers(params: ListSuppliersParams, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: supplierKeys.list(params),
    queryFn: () => listSuppliers(params),
    enabled: options?.enabled,
  })
}

export function useCreateSupplier() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateSupplierRequest) => createSupplier(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: supplierKeys.lists() })
    },
  })
}

export function useUpdateSupplier(supplierId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateSupplierRequest) => updateSupplier(supplierId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: supplierKeys.lists() })
    },
  })
}
