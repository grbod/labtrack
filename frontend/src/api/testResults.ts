import { api } from "./client"
import type { TestResult, TestResultStatus, PaginatedResponse } from "@/types"

export interface TestResultFilters {
  page?: number
  page_size?: number
  lot_id?: number
  status?: TestResultStatus
  test_type?: string
  needs_review?: boolean
}

export interface CreateTestResultData {
  lot_id: number
  test_type: string
  result_value?: string
  unit?: string
  test_date?: string
  specification?: string
  method?: string
  notes?: string
  pdf_source?: string
  confidence_score?: number
}

export interface UpdateTestResultData {
  test_type?: string
  result_value?: string
  unit?: string
  test_date?: string
  specification?: string
  method?: string
  notes?: string
}

export interface BulkCreateData {
  lot_id: number
  results: Omit<CreateTestResultData, "lot_id">[]
  pdf_source?: string
}

export const testResultsApi = {
  list: async (filters: TestResultFilters = {}): Promise<PaginatedResponse<TestResult>> => {
    const params = new URLSearchParams()
    if (filters.page) params.append("page", filters.page.toString())
    if (filters.page_size) params.append("page_size", filters.page_size.toString())
    if (filters.lot_id) params.append("lot_id", filters.lot_id.toString())
    if (filters.status) params.append("status", filters.status)
    if (filters.test_type) params.append("test_type", filters.test_type)
    if (filters.needs_review !== undefined) params.append("needs_review", filters.needs_review.toString())

    const response = await api.get<PaginatedResponse<TestResult>>(`/test-results?${params}`)
    return response.data
  },

  get: async (id: number): Promise<TestResult> => {
    const response = await api.get<TestResult>(`/test-results/${id}`)
    return response.data
  },

  getPendingCount: async (): Promise<{ pending_count: number }> => {
    const response = await api.get<{ pending_count: number }>("/test-results/pending-review")
    return response.data
  },

  create: async (data: CreateTestResultData): Promise<TestResult> => {
    const response = await api.post<TestResult>("/test-results", data)
    return response.data
  },

  bulkCreate: async (data: BulkCreateData): Promise<TestResult[]> => {
    const response = await api.post<TestResult[]>("/test-results/bulk", data)
    return response.data
  },

  update: async (id: number, data: UpdateTestResultData): Promise<TestResult> => {
    const response = await api.patch<TestResult>(`/test-results/${id}`, data)
    return response.data
  },

  updateStatus: async (id: number, status: TestResultStatus, notes?: string): Promise<TestResult> => {
    const response = await api.patch<TestResult>(`/test-results/${id}/status`, { status, notes })
    return response.data
  },

  bulkApprove: async (resultIds: number[], status: TestResultStatus): Promise<TestResult[]> => {
    const response = await api.post<TestResult[]>("/test-results/bulk-approve", {
      result_ids: resultIds,
      status,
    })
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/test-results/${id}`)
  },
}
