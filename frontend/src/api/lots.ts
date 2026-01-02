import { api } from "./client"
import type { Lot, LotWithProducts, LotType, LotStatus, PaginatedResponse } from "@/types"

export interface LotFilters {
  page?: number
  page_size?: number
  search?: string
  status?: LotStatus
  lot_type?: LotType
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
    if (filters.lot_type) params.append("lot_type", filters.lot_type)

    const response = await api.get<PaginatedResponse<Lot>>(`/lots?${params}`)
    return response.data
  },

  get: async (id: number): Promise<LotWithProducts> => {
    const response = await api.get<LotWithProducts>(`/lots/${id}`)
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

  updateStatus: async (id: number, status: LotStatus): Promise<Lot> => {
    const response = await api.patch<Lot>(`/lots/${id}/status`, { status })
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
}
