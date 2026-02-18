import { api } from "./client"

type DaaneCocDownload = {
  blob: Blob
  filename: string
  testCount: number
  testLimit: number
  limitExceeded: boolean
}

const getLimitInfo = (headers: Record<string, unknown>) => {
  const headerValue = (key: string) => {
    const value = headers[key]
    if (Array.isArray(value)) return value[0]
    if (value == null) return undefined
    return String(value)
  }
  const testCount = Number(headerValue("x-daane-test-count") ?? 0)
  const testLimit = Number(headerValue("x-daane-test-limit") ?? 12)
  const limitExceeded = (headerValue("x-daane-test-limit-exceeded") ?? "false") === "true"
  return { testCount, testLimit, limitExceeded }
}

export const daaneCocApi = {
  downloadLotCoc: async (lotId: number): Promise<DaaneCocDownload> => {
    const response = await api.get(`/lots/${lotId}/daane-coc`, {
      responseType: "blob",
    })

    const contentDisposition = response.headers["content-disposition"]
    let filename = `daane-coc-${lotId}.xlsx`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^";\n]+)"?/)
      if (match?.[1]) filename = match[1]
    }

    return { blob: response.data, filename, ...getLimitInfo(response.headers) }
  },

  downloadLotCocPdf: async (
    lotId: number,
    selectedLabTestTypeIds?: number[],
    specialInstructions?: string,
  ): Promise<DaaneCocDownload> => {
    const params = new URLSearchParams()
    selectedLabTestTypeIds?.forEach((id) => {
      params.append("selected_lab_test_type_ids", id.toString())
    })
    if (specialInstructions !== undefined) {
      params.append("special_instructions", specialInstructions)
    }

    const response = await api.get(`/lots/${lotId}/daane-coc/pdf`, {
      responseType: "blob",
      params,
    })

    const contentDisposition = response.headers["content-disposition"]
    let filename = `daane-coc-${lotId}.pdf`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^";\n]+)"?/)
      if (match?.[1]) filename = match[1]
    }

    return { blob: response.data, filename, ...getLimitInfo(response.headers) }
  },

  downloadRetestCoc: async (requestId: number): Promise<DaaneCocDownload> => {
    const response = await api.get(`/retest/retest-requests/${requestId}/daane-coc`, {
      responseType: "blob",
    })

    const contentDisposition = response.headers["content-disposition"]
    let filename = `daane-coc-retest-${requestId}.xlsx`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^";\n]+)"?/)
      if (match?.[1]) filename = match[1]
    }

    return { blob: response.data, filename, ...getLimitInfo(response.headers) }
  },

  downloadRetestCocPdf: async (requestId: number, specialInstructions?: string): Promise<DaaneCocDownload> => {
    const params = new URLSearchParams()
    if (specialInstructions !== undefined) {
      params.append("special_instructions", specialInstructions)
    }

    const response = await api.get(`/retest/retest-requests/${requestId}/daane-coc/pdf`, {
      responseType: "blob",
      params,
    })

    const contentDisposition = response.headers["content-disposition"]
    let filename = `daane-coc-retest-${requestId}.pdf`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^";\n]+)"?/)
      if (match?.[1]) filename = match[1]
    }

    return { blob: response.data, filename, ...getLimitInfo(response.headers) }
  },
}
