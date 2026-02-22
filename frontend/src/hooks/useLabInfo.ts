import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { labInfoApi, type LabInfo, type LabInfoUpdate } from "@/api/labInfo"
import { extractApiErrorMessage } from "@/lib/api-utils"

/**
 * Hook for managing lab info settings.
 * Provides fetching, updating, and logo management capabilities.
 */
export function useLabInfo() {
  const queryClient = useQueryClient()

  // Fetch lab info
  const {
    data: labInfo,
    isLoading,
    error,
  } = useQuery<LabInfo>({
    queryKey: ["labInfo"],
    queryFn: labInfoApi.get,
  })

  // Update lab info mutation
  const updateMutation = useMutation({
    mutationFn: (data: LabInfoUpdate) => labInfoApi.update(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["labInfo"] })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update lab info"))
    },
  })

  // Upload logo mutation
  const uploadLogoMutation = useMutation({
    mutationFn: (file: File) => labInfoApi.uploadLogo(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["labInfo"] })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to upload logo"))
    },
  })

  // Delete logo mutation
  const deleteLogoMutation = useMutation({
    mutationFn: () => labInfoApi.deleteLogo(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["labInfo"] })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to delete logo"))
    },
  })

  return {
    labInfo,
    isLoading,
    error,
    updateMutation,
    uploadLogoMutation,
    deleteLogoMutation,
  }
}
