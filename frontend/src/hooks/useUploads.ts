import { useMutation, useQueryClient } from "@tanstack/react-query"
import { uploadsApi, type UploadResponse } from "@/api/uploads"
import { testResultKeys } from "./useTestResults"
import { lotKeys } from "./useLots"

/**
 * Hook for uploading PDF files
 * Invalidates test results and lot details after successful upload
 */
export function useUploadPdf() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ file, lotId }: { file: File; lotId?: number }) =>
      uploadsApi.uploadPdf(file, lotId),
    onSuccess: (_, variables) => {
      // Invalidate test results to refresh PDF sources
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
      // Invalidate lot details to refresh attached PDFs
      if (variables.lotId) {
        queryClient.invalidateQueries({ queryKey: lotKeys.detailWithSpecs(variables.lotId) })
      }
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
