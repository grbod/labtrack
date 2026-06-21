import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { resultImportsApi } from "@/api/resultImports"
import type { ConfirmResultImportRequest, ResultImport } from "@/types"
import { extractApiErrorMessage } from "@/lib/api-utils"

export const resultImportKeys = {
  all: ["result-imports"] as const,
  list: () => [...resultImportKeys.all, "list"] as const,
  detail: (id: number) => [...resultImportKeys.all, "detail", id] as const,
  candidates: (search: string) => [...resultImportKeys.all, "candidates", search] as const,
  preview: (id: number, lotId: number) => [...resultImportKeys.all, "preview", id, lotId] as const,
}

export function useResultImports() {
  return useQuery({
    queryKey: resultImportKeys.list(),
    queryFn: () => resultImportsApi.list(),
    refetchInterval: (query) => {
      const data = query.state.data
      return data?.items.some((item: ResultImport) => item.status === "processing") ? 2500 : false
    },
  })
}

export function useResultImport(id: number | null) {
  return useQuery({
    queryKey: id ? resultImportKeys.detail(id) : [...resultImportKeys.all, "empty"],
    queryFn: () => resultImportsApi.get(id as number),
    enabled: id !== null,
    refetchInterval: (query) => query.state.data?.status === "processing" ? 2500 : false,
  })
}

export function useLinkCandidates(search: string) {
  return useQuery({
    queryKey: resultImportKeys.candidates(search),
    queryFn: () => resultImportsApi.linkCandidates(search),
    enabled: search.trim().length >= 2,
  })
}

export function useResultImportPreview(id: number | null, lotId: number | null) {
  return useQuery({
    queryKey: id && lotId ? resultImportKeys.preview(id, lotId) : [...resultImportKeys.all, "preview", "empty"],
    queryFn: () => resultImportsApi.preview(id as number, lotId as number),
    enabled: !!id && !!lotId,
  })
}

export function useUploadResultImports() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: resultImportsApi.upload,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: resultImportKeys.all })
      if (data.duplicates.length > 0) {
        const first = data.duplicates[0].duplicate_summary
        const detail = first?.reference_number
          ? `${first.reference_number} / ${first.lot_number || "unknown lot"}`
          : data.duplicates[0].original_filename
        toast.warning(`${data.duplicates.length} PDF${data.duplicates.length === 1 ? "" : "s"} already imported`, {
          description: detail,
        })
      }
      if (data.items.length > 0) {
        toast.success(`${data.items.length} PDF${data.items.length === 1 ? "" : "s"} queued`)
      }
    },
    onError: (error) => toast.error(extractApiErrorMessage(error, "Failed to upload PDFs")),
  })
}

export function useConfirmResultImport(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ConfirmResultImportRequest) => resultImportsApi.confirm(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: resultImportKeys.all })
      toast.success("Results applied as drafts")
    },
    onError: (error) => toast.error(extractApiErrorMessage(error, "Failed to confirm import")),
  })
}

export function useRetryResultImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: resultImportsApi.retry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: resultImportKeys.all })
      toast.success("Import re-queued")
    },
    onError: (error) => toast.error(extractApiErrorMessage(error, "Failed to retry import")),
  })
}

export function useCancelResultImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: resultImportsApi.cancel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: resultImportKeys.all })
      toast.success("Import cancelled")
    },
    onError: (error) => toast.error(extractApiErrorMessage(error, "Failed to cancel import")),
  })
}

export function useRevertResultImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: resultImportsApi.revert,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: resultImportKeys.all })
      toast.success("Import reverted")
    },
    onError: (error) => toast.error(extractApiErrorMessage(error, "Failed to revert import")),
  })
}
