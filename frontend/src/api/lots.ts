import { api } from "./client"
import type { Lot, LotWithProducts, LotWithProductSpecs, LotType, LotStatus, PaginatedResponse, ArchivedLot } from "@/types"

export interface LotFilters {
  page?: number
  page_size?: number
  search?: string
  status?: LotStatus
  exclude_statuses?: LotStatus[]
  lot_type?: LotType
}

export interface ArchivedLotFilters {
  page?: number
  page_size?: number
  search?: string
  status?: 'released' | 'rejected'
  date_from?: string
  date_to?: string
}

export interface ProductReference {
  product_id: number
  percentage?: number
}

export interface CreateLotData {
  lot_number: string
  lot_type: LotType
  mfg_date?: string
  exp_date?: string
  generate_coa?: boolean
  products?: ProductReference[]
  reference_number?: string
}

export interface UpdateLotData {
  lot_number?: string
  mfg_date?: string
  exp_date?: string
  generate_coa?: boolean
  status?: LotStatus
}

export interface SublotData {
  sublot_number: string
  production_date?: string
  quantity_lbs?: number
}

export interface Sublot {
  id: number
  parent_lot_id: number
  sublot_number: string
  production_date?: string
  quantity_lbs?: number
  created_at: string
}

export const lotsApi = {
  list: async (filters: LotFilters = {}): Promise<PaginatedResponse<Lot>> => {
    const params = new URLSearchParams()
    if (filters.page) params.append("page", filters.page.toString())
    if (filters.page_size) params.append("page_size", filters.page_size.toString())
    if (filters.search) params.append("search", filters.search)
    if (filters.status) params.append("status", filters.status)
    if (filters.exclude_statuses) {
      filters.exclude_statuses.forEach(status => params.append("exclude_statuses", status))
    }
    if (filters.lot_type) params.append("lot_type", filters.lot_type)

    const response = await api.get<PaginatedResponse<Lot>>(`/lots?${params}`)
    return response.data
  },

  get: async (id: number): Promise<LotWithProducts> => {
    const response = await api.get<LotWithProducts>(`/lots/${id}`)
    return response.data
  },

  /** Get lot with products and their test specifications (for Sample Modal) */
  getWithSpecs: async (id: number): Promise<LotWithProductSpecs> => {
    const response = await api.get<LotWithProductSpecs>(`/lots/${id}/with-specs`)
    return response.data
  },

  getStatusCounts: async (): Promise<Record<string, number>> => {
    const response = await api.get<Record<string, number>>("/lots/status-counts")
    return response.data
  },

  create: async (data: CreateLotData): Promise<Lot> => {
    const response = await api.post<Lot>("/lots", data)
    return response.data
  },

  update: async (id: number, data: UpdateLotData): Promise<Lot> => {
    const response = await api.patch<Lot>(`/lots/${id}`, data)
    return response.data
  },

  updateStatus: async (
    id: number,
    status: LotStatus,
    rejectionReason?: string,
    overrideReason?: string
  ): Promise<Lot> => {
    const response = await api.patch<Lot>(`/lots/${id}/status`, {
      status,
      rejection_reason: rejectionReason,
      override_reason: overrideReason,
    })
    return response.data
  },

  submitForReview: async (id: number, overrideUserId?: number): Promise<Lot> => {
    const params = overrideUserId ? { override_user_id: overrideUserId } : {}
    const response = await api.post<Lot>(`/lots/${id}/submit-for-review`, null, { params })
    return response.data
  },

  resubmit: async (id: number): Promise<Lot> => {
    const response = await api.post<Lot>(`/lots/${id}/resubmit`)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/lots/${id}`)
  },

  // Sublot operations
  listSublots: async (lotId: number): Promise<Sublot[]> => {
    const response = await api.get<Sublot[]>(`/lots/${lotId}/sublots`)
    return response.data
  },

  createSublot: async (lotId: number, data: SublotData): Promise<Sublot> => {
    const response = await api.post<Sublot>(`/lots/${lotId}/sublots`, data)
    return response.data
  },

  createSublotsBulk: async (lotId: number, sublots: SublotData[]): Promise<Sublot[]> => {
    const response = await api.post<Sublot[]>(`/lots/${lotId}/sublots/bulk`, { sublots })
    return response.data
  },

  /** List archived (completed) lots for historical view */
  listArchived: async (filters: ArchivedLotFilters = {}): Promise<PaginatedResponse<ArchivedLot>> => {
    const params = new URLSearchParams()
    if (filters.page) params.append("page", filters.page.toString())
    if (filters.page_size) params.append("page_size", filters.page_size.toString())
    if (filters.search) params.append("search", filters.search)
    if (filters.status) params.append("status", filters.status)
    if (filters.date_from) params.append("date_from", filters.date_from)
    if (filters.date_to) params.append("date_to", filters.date_to)

    const response = await api.get<PaginatedResponse<ArchivedLot>>(`/lots/archived?${params}`)
    return response.data
  },
}
