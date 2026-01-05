import { api } from "./client"
import type { Customer, PaginatedResponse } from "@/types"

export interface CustomerFilters {
  page?: number
  page_size?: number
  search?: string
  include_inactive?: boolean
}

export interface CreateCustomerData {
  company_name: string
  contact_name: string
  email: string
}

export interface UpdateCustomerData {
  company_name?: string
  contact_name?: string
  email?: string
}

export const customersApi = {
  list: async (filters: CustomerFilters = {}): Promise<PaginatedResponse<Customer>> => {
    const params = new URLSearchParams()
    if (filters.page) params.append("page", filters.page.toString())
    if (filters.page_size) params.append("page_size", filters.page_size.toString())
    if (filters.search) params.append("search", filters.search)
    if (filters.include_inactive) params.append("include_inactive", "true")

    const response = await api.get<PaginatedResponse<Customer>>(`/customers?${params}`)
    return response.data
  },

  get: async (id: number): Promise<Customer> => {
    const response = await api.get<Customer>(`/customers/${id}`)
    return response.data
  },

  create: async (data: CreateCustomerData): Promise<Customer> => {
    const response = await api.post<Customer>("/customers", data)
    return response.data
  },

  update: async (id: number, data: UpdateCustomerData): Promise<Customer> => {
    const response = await api.patch<Customer>(`/customers/${id}`, data)
    return response.data
  },

  deactivate: async (id: number): Promise<void> => {
    await api.delete(`/customers/${id}`)
  },

  activate: async (id: number): Promise<Customer> => {
    const response = await api.post<Customer>(`/customers/${id}/activate`)
    return response.data
  },
}
