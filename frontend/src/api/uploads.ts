import { api } from "./client"

export interface UploadResponse {
  filename: string
  original_filename: string
  key: string  // Storage key (R2 or local path)
  size: number
  content_type: string
}

export const uploadsApi = {
  /**
   * Fetch a PDF as a blob (with auth) and open in new window
   */
  openPdf: async (filename: string): Promise<void> => {
    const response = await api.get(`/uploads/${encodeURIComponent(filename)}`, {
      responseType: "blob",
    })
    const blob = new Blob([response.data], { type: "application/pdf" })
    const url = URL.createObjectURL(blob)
    window.open(url, "_blank")
    // Clean up the URL after a delay to allow the new tab to load
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  },

  /**
   * Upload a PDF file and associate it with a lot
   * Returns metadata including the filename
   */
  uploadPdf: async (file: File, lotId?: number): Promise<UploadResponse> => {
    const formData = new FormData()
    formData.append("file", file)
    if (lotId) {
      formData.append("lot_id", lotId.toString())
    }

    const response = await api.post<UploadResponse>("/uploads/pdf", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    })
    return response.data
  },

  /**
   * Delete an uploaded file
   */
  deleteUpload: async (filename: string): Promise<void> => {
    await api.delete(`/uploads/${filename}`)
  },
}
