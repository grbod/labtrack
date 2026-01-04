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
   * Upload a PDF file
   * Returns metadata including the filename to store in test result
   */
  uploadPdf: async (file: File): Promise<UploadResponse> => {
    const formData = new FormData()
    formData.append("file", file)

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
