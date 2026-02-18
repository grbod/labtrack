import { api } from "./client"
import type { RetestRequest, RetestRequestListResponse, CreateRetestRequestData, RetestOriginalValue } from "@/types"

export const retestsApi = {
  /**
   * Create a new retest request for a lot
   */
  create: async (lotId: number, data: CreateRetestRequestData): Promise<RetestRequest> => {
    const response = await api.post<RetestRequest>(`/retest/lots/${lotId}/retest-requests`, data)
    return response.data
  },

  /**
   * Get all retest requests for a lot
   */
  getForLot: async (lotId: number): Promise<RetestRequestListResponse> => {
    const response = await api.get<RetestRequestListResponse>(`/retest/lots/${lotId}/retest-requests`)
    return response.data
  },

  /**
   * Get a specific retest request by ID
   */
  get: async (requestId: number): Promise<RetestRequest> => {
    const response = await api.get<RetestRequest>(`/retest/retest-requests/${requestId}`)
    return response.data
  },

  /**
   * Download retest request PDF
   */
  downloadPdf: async (requestId: number): Promise<void> => {
    const response = await api.get(`/retest/retest-requests/${requestId}/pdf`, {
      responseType: "blob",
    })

    // Create a download link
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement("a")
    link.href = url
    link.setAttribute("download", `retest-request-${requestId}.pdf`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },

  /**
   * Get PDF as blob URL for preview
   */
  getPdfUrl: async (requestId: number): Promise<string> => {
    const response = await api.get(`/retest/retest-requests/${requestId}/pdf`, {
      responseType: "blob",
    })
    return window.URL.createObjectURL(new Blob([response.data], { type: "application/pdf" }))
  },

  /**
   * Manually complete a retest request
   */
  complete: async (requestId: number): Promise<RetestRequest> => {
    const response = await api.post<RetestRequest>(`/retest/retest-requests/${requestId}/complete`)
    return response.data
  },

  /**
   * Get retest history for a specific test result
   */
  getTestResultHistory: async (testResultId: number): Promise<RetestOriginalValue[]> => {
    const response = await api.get<RetestOriginalValue[]>(`/retest/test-results/${testResultId}/retest-history`)
    return response.data
  },
}
