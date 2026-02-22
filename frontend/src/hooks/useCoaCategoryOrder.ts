import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  coaCategoryOrderApi,
  type UpdateCOACategoryOrderData,
} from "@/api/coaCategoryOrder"
import { extractApiErrorMessage } from "@/lib/api-utils"

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
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update category order"))
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
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to reset category order"))
    },
  })
}
