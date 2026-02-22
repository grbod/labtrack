import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { labMappingApi } from "@/api/labMapping"
import { extractApiErrorMessage } from "@/lib/api-utils"

export const labMappingKeys = {
  all: ["labMapping"] as const,
}

export function useLabMapping(enabled: boolean = true) {
  return useQuery({
    queryKey: labMappingKeys.all,
    queryFn: () => labMappingApi.get(),
    enabled,
  })
}

export function useRebuildLabMapping() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => labMappingApi.rebuild(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: labMappingKeys.all })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to rebuild lab mapping"))
    },
  })
}
