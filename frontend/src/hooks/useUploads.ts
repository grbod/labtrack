import { useMutation, useQueryClient } from "@tanstack/react-query"
import { uploadsApi, type UploadResponse } from "@/api/uploads"
import { testResultKeys } from "./useTestResults"

/**
 * Hook for uploading PDF files
 * Invalidates test results after successful upload
 */
export function useUploadPdf() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (file: File) => uploadsApi.uploadPdf(file),
    onSuccess: () => {
      // Invalidate test results to refresh PDF sources
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
    },
  })
}

/**
 * Hook for deleting uploaded files
 */
export function useDeleteUpload() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (filename: string) => uploadsApi.deleteUpload(filename),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
    },
  })
}

export type { UploadResponse }
