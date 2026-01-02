import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  testResultsApi,
  type TestResultFilters,
  type CreateTestResultData,
  type UpdateTestResultData,
  type BulkCreateData,
} from "@/api/testResults"
import type { TestResultStatus } from "@/types"

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
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
      queryClient.invalidateQueries({ queryKey: testResultKeys.detail(variables.id) })
    },
  })
}

export function useApproveTestResult() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, status, notes }: { id: number; status: TestResultStatus; notes?: string }) =>
      testResultsApi.updateStatus(id, status, notes),
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: testResultKeys.lists() })
      queryClient.invalidateQueries({ queryKey: testResultKeys.pendingCount() })
    },
  })
}
