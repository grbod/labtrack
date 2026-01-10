import { api } from "./client"

export interface UploadResponse {
  filename: string
  original_filename: string
  path: string
  size: number
  content_type: string
}

export const uploadsApi = {
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
