import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { labInfoApi, type LabInfo, type LabInfoUpdate } from "@/api/labInfo"

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
  })

  // Upload logo mutation
  const uploadLogoMutation = useMutation({
    mutationFn: (file: File) => labInfoApi.uploadLogo(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["labInfo"] })
    },
  })

  // Delete logo mutation
  const deleteLogoMutation = useMutation({
    mutationFn: () => labInfoApi.deleteLogo(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["labInfo"] })
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
