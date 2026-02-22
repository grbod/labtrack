import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  testResultsApi,
  type TestResultFilters,
  type CreateTestResultData,
  type UpdateTestResultData,
  type BulkCreateData,
} from "@/api/testResults"
import { extractApiErrorMessage } from "@/lib/api-utils"
import type { TestResultStatus } from "@/types"
import { retestKeys } from "@/hooks/useRetests"

export const testResultKeys = {
  all: ["testResults"] as const,
  lists: () => [...testResultKeys.all, "list"] as const,
  list: (filters: TestResultFilters) => [...testResultKeys.lists(), filters] as const,
  details: () => [...testResultKeys.all, "detail"] as const,
  detail: (id: number) => [...testResultKeys.details(), id] as const,
  pendingCount: () => [...testResultKeys.all, "pendingCount"] as const,
}

export function useTestResults(filters: TestResultFilters = {}) {
  return useQuery({
    queryKey: testResultKeys.list(filters),
    queryFn: () => testResultsApi.list(filters),
  })
}

export function useTestResult(id: number) {
  return useQuery({
    queryKey: testResultKeys.detail(id),
    queryFn: () => testResultsApi.get(id),
    enabled: !!id,
  })
}

export function usePendingReviewCount() {
  return useQuery({
    queryKey: testResultKeys.pendingCount(),
    queryFn: () => testResultsApi.getPendingCount(),
  })
}

export function useCreateTestResult() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateTestResultData) => testResultsApi.create(data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to create test result"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
      queryClient.invalidateQueries({ queryKey: testResultKeys.pendingCount() })
    },
  })
}

export function useBulkCreateTestResults() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: BulkCreateData) => testResultsApi.bulkCreate(data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to bulk create test results"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
      queryClient.invalidateQueries({ queryKey: testResultKeys.pendingCount() })
    },
  })
}

export function useUpdateTestResult() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateTestResultData }) =>
      testResultsApi.update(id, data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update test result"))
    },
    onSuccess: (result, variables) => {
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
      queryClient.invalidateQueries({ queryKey: testResultKeys.detail(variables.id) })
      // Invalidate retest queries - backend may have auto-completed a retest
      if (result.lot_id) {
        queryClient.invalidateQueries({ queryKey: retestKeys.forLot(result.lot_id) })
      }
    },
  })
}

export function useApproveTestResult() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, status, notes }: { id: number; status: TestResultStatus; notes?: string }) =>
      testResultsApi.updateStatus(id, status, notes),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to approve test result"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
      queryClient.invalidateQueries({ queryKey: testResultKeys.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: testResultKeys.pendingCount() })
    },
  })
}

export function useBulkApproveTestResults() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ resultIds, status }: { resultIds: number[]; status: TestResultStatus }) =>
      testResultsApi.bulkApprove(resultIds, status),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to bulk approve test results"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
      queryClient.invalidateQueries({ queryKey: testResultKeys.pendingCount() })
    },
  })
}

export function useDeleteTestResult() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => testResultsApi.delete(id),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to delete test result"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
      queryClient.invalidateQueries({ queryKey: testResultKeys.pendingCount() })
    },
  })
}
