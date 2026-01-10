import { api } from "./client"
import type {
  ReleaseQueueItem,
  ReleaseDetails,
  ArchiveItem,
  Customer,
  EmailHistory,
  ArchiveFilters,
  SaveDraftData,
  CreateCustomerData,
  COAPreviewData,
} from "@/types/release"
import type { PaginatedResponse } from "@/types"

export const releaseApi = {
  /** Get items in the release queue (Lot+Product based) */
  getQueue: async (): Promise<ReleaseQueueItem[]> => {
    const response = await api.get<{ items: ReleaseQueueItem[]; total: number }>("/release/queue")
    return response.data.items
  },

  /** Get release details for a Lot+Product combination */
  getDetails: async (lotId: number, productId: number): Promise<ReleaseDetails> => {
    const response = await api.get<ReleaseDetails>(`/release/${lotId}/${productId}`)
    return response.data
  },

  /** Get the COA PDF preview URL for a lot/product */
  getPreviewUrl: (lotId: number, productId: number): string => {
    return `/api/v1/release/${lotId}/${productId}/preview`
  },

  /** Get COA preview data for frontend rendering */
  getPreviewData: async (lotId: number, productId: number): Promise<COAPreviewData> => {
    const response = await api.get<COAPreviewData>(`/release/${lotId}/${productId}/preview-data`)
    return response.data
  },

  /** Get the source PDF URL for a lot/product */
  getSourcePdfUrl: (lotId: number, productId: number, filename: string): string => {
    return `/api/v1/release/${lotId}/${productId}/source-pdfs/${encodeURIComponent(filename)}`
  },

  /** Get source PDF as blob (with auth token) */
  getSourcePdfBlob: async (lotId: number, productId: number, filename: string): Promise<Blob> => {
    const response = await api.get(`/release/${lotId}/${productId}/source-pdfs/${encodeURIComponent(filename)}`, {
      responseType: "blob",
    })
    return response.data
  },

  /** Save draft data (customer_id, notes) for a lot/product */
  saveDraft: async (lotId: number, productId: number, data: SaveDraftData): Promise<ReleaseDetails> => {
    const response = await api.put<ReleaseDetails>(`/release/${lotId}/${productId}/draft`, data)
    return response.data
  },

  /** Approve and release a lot/product */
  approve: async (
    lotId: number,
    productId: number,
    customerId?: number,
    notes?: string
  ): Promise<ReleaseDetails> => {
    const response = await api.post<ReleaseDetails>(`/release/${lotId}/${productId}/approve`, {
      customer_id: customerId,
      notes,
    })
    return response.data
  },

  /** Log an email sent for this lot/product */
  sendEmail: async (lotId: number, productId: number, recipientEmail: string): Promise<EmailHistory> => {
    const response = await api.post<EmailHistory>(`/release/${lotId}/${productId}/email`, {
      recipient_email: recipientEmail,
    })
    return response.data
  },

  /** Get email history for a lot/product */
  getEmailHistory: async (lotId: number, productId: number): Promise<EmailHistory[]> => {
    const response = await api.get<EmailHistory[]>(`/release/${lotId}/${productId}/emails`)
    return response.data
  },

  /** Search archived (released) COAs */
  searchArchive: async (filters: ArchiveFilters = {}): Promise<PaginatedResponse<ArchiveItem>> => {
    const params = new URLSearchParams()
    if (filters.search) params.append("search", filters.search)
    if (filters.product_id) params.append("product_id", filters.product_id.toString())
    if (filters.customer_id) params.append("customer_id", filters.customer_id.toString())
    if (filters.date_from) params.append("date_from", filters.date_from)
    if (filters.date_to) params.append("date_to", filters.date_to)
    if (filters.lot_number) params.append("lot_number", filters.lot_number)
    if (filters.page) params.append("page", filters.page.toString())
    if (filters.page_size) params.append("page_size", filters.page_size.toString())

    const response = await api.get<PaginatedResponse<ArchiveItem>>(`/archive?${params}`)
    return response.data
  },

  /** Download a released COA for a lot/product */
  getDownloadUrl: (lotId: number, productId: number): string => {
    return `/api/v1/release/${lotId}/${productId}/download`
  },

}

export const customerApi = {
  /** List all customers */
  list: async (): Promise<Customer[]> => {
    const response = await api.get<{ items: Customer[]; total: number }>("/customers")
    return response.data.items
  },

  /** Create a new customer */
  create: async (data: CreateCustomerData): Promise<Customer> => {
    const response = await api.post<Customer>("/customers", data)
    return response.data
  },
}
