import { api } from "./client"

export interface LabInfo {
  id: number
  company_name: string
  address: string
  city: string
  state: string
  zip_code: string
  phone: string
  email: string
  logo_url: string | null
  signature_url: string | null
  signer_name: string | null
  require_pdf_for_submission: boolean
  show_spec_preview_on_sample: boolean
  created_at: string
  updated_at: string
}

export interface LabInfoUpdate {
  company_name: string
  address: string
  phone?: string
  email?: string
  city: string
  state: string
  zip_code: string
  require_pdf_for_submission?: boolean
  show_spec_preview_on_sample?: boolean
}

export const labInfoApi = {
  /**
   * Get the current lab info configuration.
   */
  get: async (): Promise<LabInfo> => {
    const response = await api.get<LabInfo>("/settings/lab-info")
    return response.data
  },

  /**
   * Update lab info text fields.
   */
  update: async (data: LabInfoUpdate): Promise<LabInfo> => {
    const response = await api.put<LabInfo>("/settings/lab-info", data)
    return response.data
  },

  /**
   * Upload a new logo.
   */
  uploadLogo: async (file: File): Promise<LabInfo> => {
    const formData = new FormData()
    formData.append("file", file)
    const response = await api.post<LabInfo>("/settings/lab-info/logo", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    })
    return response.data
  },

  /**
   * Delete the current logo.
   */
  deleteLogo: async (): Promise<LabInfo> => {
    const response = await api.delete<LabInfo>("/settings/lab-info/logo")
    return response.data
  },
}
