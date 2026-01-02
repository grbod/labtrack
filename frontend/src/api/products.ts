import { api } from "./client"
import type { Product, PaginatedResponse } from "@/types"

export interface ProductFilters {
  page?: number
  page_size?: number
  search?: string
  brand?: string
  is_active?: boolean
}

export interface CreateProductData {
  brand: string
  product_name: string
  flavor?: string
  size?: string
  display_name: string
  serving_size?: number
  expiry_duration_months?: number
}

export interface UpdateProductData extends Partial<CreateProductData> {
  is_active?: boolean
}

export const productsApi = {
  list: async (filters: ProductFilters = {}): Promise<PaginatedResponse<Product>> => {
    const params = new URLSearchParams()
    if (filters.page) params.append("page", filters.page.toString())
    if (filters.page_size) params.append("page_size", filters.page_size.toString())
    if (filters.search) params.append("search", filters.search)
    if (filters.brand) params.append("brand", filters.brand)
    if (filters.is_active !== undefined) params.append("is_active", filters.is_active.toString())

    const response = await api.get<PaginatedResponse<Product>>(`/products?${params}`)
    return response.data
  },

  get: async (id: number): Promise<Product> => {
    const response = await api.get<Product>(`/products/${id}`)
    return response.data
  },

  getBrands: async (): Promise<string[]> => {
    const response = await api.get<string[]>("/products/brands")
    return response.data
  },

  create: async (data: CreateProductData): Promise<Product> => {
    const response = await api.post<Product>("/products", data)
    return response.data
  },

  update: async (id: number, data: UpdateProductData): Promise<Product> => {
    const response = await api.patch<Product>(`/products/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/products/${id}`)
  },
}
