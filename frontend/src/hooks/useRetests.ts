import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { retestsApi } from "@/api/retests"
import { lotKeys } from "@/hooks/useLots"
import type { CreateRetestRequestData } from "@/types"

/** Invalidate all lot-related queries after retest changes */
function invalidateLotQueries(queryClient: ReturnType<typeof useQueryClient>, lotId: number) {
  queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
  queryClient.invalidateQueries({ queryKey: lotKeys.detail(lotId) })
  queryClient.invalidateQueries({ queryKey: lotKeys.detailWithSpecs(lotId) })
}

export const retestKeys = {
  all: ["retests"] as const,
  forLot: (lotId: number) => [...retestKeys.all, "lot", lotId] as const,
  detail: (requestId: number) => [...retestKeys.all, "detail", requestId] as const,
  testResultHistory: (testResultId: number) => [...retestKeys.all, "test-result", testResultId] as const,
}

/**
 * Get all retest requests for a lot
 */
export function useRetestRequests(lotId: number) {
  return useQuery({
    queryKey: retestKeys.forLot(lotId),
    queryFn: () => retestsApi.getForLot(lotId),
    enabled: lotId > 0,
  })
}

/**
 * Get a specific retest request
 */
export function useRetestRequest(requestId: number) {
  return useQuery({
    queryKey: retestKeys.detail(requestId),
    queryFn: () => retestsApi.get(requestId),
    enabled: requestId > 0,
  })
}

/**
 * Get retest history for a specific test result
 */
export function useTestResultRetestHistory(testResultId: number) {
  return useQuery({
    queryKey: retestKeys.testResultHistory(testResultId),
    queryFn: () => retestsApi.getTestResultHistory(testResultId),
    enabled: testResultId > 0,
  })
}

/**
 * Create a new retest request
 */
export function useCreateRetestRequest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ lotId, data }: { lotId: number; data: CreateRetestRequestData }) =>
      retestsApi.create(lotId, data),
    onSuccess: (_, variables) => {
      // Invalidate retest requests for this lot
      queryClient.invalidateQueries({ queryKey: retestKeys.forLot(variables.lotId) })
      // Invalidate lot data to update has_pending_retest flag
      invalidateLotQueries(queryClient, variables.lotId)
      // Invalidate test result retest history
      variables.data.test_result_ids.forEach(testResultId => {
        queryClient.invalidateQueries({ queryKey: retestKeys.testResultHistory(testResultId) })
      })
    },
  })
}

/**
 * Complete a retest request manually
 */
export function useCompleteRetestRequest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (requestId: number) => retestsApi.complete(requestId),
    onSuccess: (result) => {
      // Invalidate retest requests for this lot
      queryClient.invalidateQueries({ queryKey: retestKeys.forLot(result.lot_id) })
      queryClient.invalidateQueries({ queryKey: retestKeys.detail(result.id) })
      // Invalidate lot data to update has_pending_retest flag
      invalidateLotQueries(queryClient, result.lot_id)
    },
  })
}

/**
 * Download retest request PDF
 */
export function useDownloadRetestPdf() {
  return useMutation({
    mutationFn: (requestId: number) => retestsApi.downloadPdf(requestId),
  })
}
