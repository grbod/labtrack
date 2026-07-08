import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  labTestAliasesApi,
  type LabTestAliasFilters,
  type UpdateLabTestAliasData,
} from "@/api/labTestAliases"
import { extractApiErrorMessage } from "@/lib/api-utils"

export const labTestAliasKeys = {
  all: ["labTestAliases"] as const,
  lists: () => [...labTestAliasKeys.all, "list"] as const,
  list: (filters: LabTestAliasFilters) => [...labTestAliasKeys.lists(), filters] as const,
  builtins: () => [...labTestAliasKeys.all, "builtins"] as const,
}

export function useLabTestAliases(
  filters: LabTestAliasFilters = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: labTestAliasKeys.list(filters),
    queryFn: () => labTestAliasesApi.list(filters),
    enabled: options?.enabled ?? true,
  })
}

export function useLabTestBuiltinAliases(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: labTestAliasKeys.builtins(),
    queryFn: () => labTestAliasesApi.listBuiltins(),
    enabled: options?.enabled ?? true,
  })
}

export function useUpdateLabTestAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateLabTestAliasData }) =>
      labTestAliasesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: labTestAliasKeys.lists() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update alias"))
    },
  })
}

export function useApproveLabTestAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => labTestAliasesApi.approve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: labTestAliasKeys.lists() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to approve alias"))
    },
  })
}

export function useDisableLabTestAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      labTestAliasesApi.disable(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: labTestAliasKeys.lists() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to disable alias"))
    },
  })
}
