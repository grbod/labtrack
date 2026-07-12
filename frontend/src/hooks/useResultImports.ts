import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { resultImportsApi } from "@/api/resultImports"
import { lotKeys } from "@/hooks/useLots"
import { releaseKeys } from "@/hooks/useRelease"
import type {
  ConfirmResultImportRequest,
  ResultImport,
  ResultImportPreviewOverride,
} from "@/types"
import { extractApiErrorMessage } from "@/lib/api-utils"

/**
 * Stable serialization of preview lab-type overrides for use in the query key.
 * Sorted by row_id so key identity depends only on the override *set*, not the
 * order the operator mapped rows in. `null` (an explicit clear-to-unmapped) is a
 * meaningful override and is preserved.
 */
export function serializePreviewOverrides(overrides: ResultImportPreviewOverride[]): string {
  return JSON.stringify(
    [...overrides]
      .sort((a, b) => a.row_id.localeCompare(b.row_id))
      .map((o) => [o.row_id, o.lab_test_type_id])
  )
}

export const resultImportKeys = {
  all: ["result-imports"] as const,
  list: () => [...resultImportKeys.all, "list"] as const,
  stats: () => [...resultImportKeys.all, "stats"] as const,
  detail: (id: number) => [...resultImportKeys.all, "detail", id] as const,
  candidates: (search: string) => [...resultImportKeys.all, "candidates", search] as const,
  preview: (id: number, lotId: number, overridesKey = "[]") =>
    [...resultImportKeys.all, "preview", id, lotId, overridesKey] as const,
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

export function useResultImportStats() {
  return useQuery({
    queryKey: resultImportKeys.stats(),
    queryFn: () => resultImportsApi.stats(),
    // Keep the dashboard tile fresh while extractions are in flight.
    refetchInterval: (query) =>
      (query.state.data?.processing ?? 0) > 0 ? 2500 : 15000,
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

export function useResultImportPreview(
  id: number | null,
  lotId: number | null,
  overrides: ResultImportPreviewOverride[] = []
) {
  const overridesKey = serializePreviewOverrides(overrides)
  const hasOverrides = overrides.length > 0
  return useQuery({
    queryKey:
      id && lotId
        ? resultImportKeys.preview(id, lotId, overridesKey)
        : [...resultImportKeys.all, "preview", "empty"],
    // POST the re-resolved preview when the operator has remapped rows, so
    // existing_result/suggested_action reflect the overridden lab types; plain
    // GET otherwise. The overrides are baked into the query key, so cached data
    // is always for the exact (lot, overrides) pair it was fetched with.
    queryFn: () =>
      hasOverrides
        ? resultImportsApi.previewWithOverrides(id as number, lotId as number, overrides)
        : resultImportsApi.preview(id as number, lotId as number),
    enabled: !!id && !!lotId,
  })
}

export function useUploadResultImports(onDuplicateSelect?: (importId: number) => void) {
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
        onDuplicateSelect?.(data.duplicates[0].id)
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
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: resultImportKeys.all })
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(result.lot_id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.detailWithSpecs(result.lot_id) })
      queryClient.invalidateQueries({ queryKey: releaseKeys.queue() })

      const applied = result.created_result_ids?.length ?? 0
      const replaced = result.updated_result_ids?.length ?? 0
      const skipped = result.skipped_row_ids?.length ?? 0
      const segments: string[] = []
      if (applied) segments.push(`${applied} applied`)
      if (replaced) segments.push(`${replaced} replaced`)
      if (skipped) segments.push(`${skipped} skipped`)
      const message = segments.length ? segments.join(", ") : "No changes applied"
      if (skipped > 0) toast.warning(message)
      else toast.success(message)

      const aliasSuggestions = result.alias_suggestions_created ?? 0
      if (aliasSuggestions > 0) {
        toast.info(
          `${aliasSuggestions} test-name alias suggestion${aliasSuggestions === 1 ? "" : "s"} recorded for QC review under Lab Test Types.`
        )
      }
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
