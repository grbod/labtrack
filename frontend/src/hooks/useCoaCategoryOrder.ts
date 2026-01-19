import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  coaCategoryOrderApi,
  type UpdateCOACategoryOrderData,
} from "@/api/coaCategoryOrder"

export const coaCategoryOrderKeys = {
  all: ["coaCategoryOrder"] as const,
  order: () => [...coaCategoryOrderKeys.all, "order"] as const,
  activeCategories: () => [...coaCategoryOrderKeys.all, "activeCategories"] as const,
}

export function useCoaCategoryOrder() {
  return useQuery({
    queryKey: coaCategoryOrderKeys.order(),
    queryFn: () => coaCategoryOrderApi.get(),
  })
}

export function useActiveCategories() {
  return useQuery({
    queryKey: coaCategoryOrderKeys.activeCategories(),
    queryFn: () => coaCategoryOrderApi.getActiveCategories(),
  })
}

export function useUpdateCoaCategoryOrder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: UpdateCOACategoryOrderData) => coaCategoryOrderApi.update(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: coaCategoryOrderKeys.order() })
      queryClient.invalidateQueries({ queryKey: coaCategoryOrderKeys.activeCategories() })
    },
  })
}

export function useResetCoaCategoryOrder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => coaCategoryOrderApi.reset(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: coaCategoryOrderKeys.order() })
      queryClient.invalidateQueries({ queryKey: coaCategoryOrderKeys.activeCategories() })
    },
  })
}
