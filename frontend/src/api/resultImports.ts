import { api } from "./client"
import type {
  ConfirmResultImportRequest,
  ConfirmResultImportResponse,
  LinkCandidate,
  PaginatedResponse,
  ResultImport,
  ResultImportPreview,
  ResultImportUploadResponse,
} from "@/types"

export const resultImportsApi = {
  upload: async (files: File[]): Promise<ResultImportUploadResponse> => {
    const formData = new FormData()
    files.forEach((file) => formData.append("files", file))
    const response = await api.post<ResultImportUploadResponse>("/result-imports", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    return response.data
  },

  list: async (page = 1, pageSize = 25): Promise<PaginatedResponse<ResultImport>> => {
    const response = await api.get<PaginatedResponse<ResultImport>>("/result-imports", {
      params: { page, page_size: pageSize },
    })
    return response.data
  },

  get: async (id: number): Promise<ResultImport> => {
    const response = await api.get<ResultImport>(`/result-imports/${id}`)
    return response.data
  },

  linkCandidates: async (search: string): Promise<LinkCandidate[]> => {
    const response = await api.get<LinkCandidate[]>("/result-imports/link-candidates", {
      params: { search },
    })
    return response.data
  },

  preview: async (id: number, lotId: number): Promise<ResultImportPreview> => {
    const response = await api.get<ResultImportPreview>(`/result-imports/${id}/preview`, {
      params: { lot_id: lotId },
    })
    return response.data
  },

  confirm: async (
    id: number,
    payload: ConfirmResultImportRequest
  ): Promise<ConfirmResultImportResponse> => {
    const response = await api.post<ConfirmResultImportResponse>(`/result-imports/${id}/confirm`, payload)
    return response.data
  },

  retry: async (id: number): Promise<ResultImport> => {
    const response = await api.post<ResultImport>(`/result-imports/${id}/retry`)
    return response.data
  },

  cancel: async (id: number): Promise<ResultImport> => {
    const response = await api.post<ResultImport>(`/result-imports/${id}/cancel`)
    return response.data
  },

  revert: async (id: number): Promise<ResultImport> => {
    const response = await api.post<ResultImport>(`/result-imports/${id}/revert`)
    return response.data
  },

  getPdfBlob: async (storageKey: string): Promise<Blob> => {
    const response = await api.get(`/uploads/${encodeURIComponent(storageKey)}`, {
      responseType: "blob",
    })
    return response.data
  },
}
