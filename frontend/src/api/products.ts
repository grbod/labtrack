import { api } from "./client"
import type { Product, ProductSize, ProductWithSpecs, ProductTestSpecification, PaginatedResponse } from "@/types"

export interface ProductFilters {
  page?: number
  page_size?: number
  search?: string
  brand?: string
}

export interface CreateProductData {
  brand: string
  product_name: string
  flavor?: string
  size?: string
  display_name: string
  serving_size?: string  // e.g., "30g", "2 capsules", "1 tsp"
  expiry_duration_months?: number
}

export interface UpdateProductData extends Partial<CreateProductData> {}

export interface CreateTestSpecData {
  lab_test_type_id: number
  specification: string
  is_required: boolean
}

export interface UpdateTestSpecData {
  specification?: string
  is_required?: boolean
}

export interface BulkImportProductRow {
  brand: string
  product_name: string
  display_name: string
  flavor?: string
  size?: string
  serving_size?: string
  expiry_duration_months?: number
}

export interface BulkImportResult {
  total_rows: number
  imported: number
  skipped: number
  errors: string[]
}

export interface CreateSizeData {
  size: string
}

export interface UpdateSizeData {
  size: string
}

export const productsApi = {
  list: async (filters: ProductFilters = {}): Promise<PaginatedResponse<Product>> => {
    const params = new URLSearchParams()
    if (filters.page) params.append("page", filters.page.toString())
    if (filters.page_size) params.append("page_size", filters.page_size.toString())
    if (filters.search) params.append("search", filters.search)
    if (filters.brand) params.append("brand", filters.brand)

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

  // Get product with test specifications
  getWithSpecs: async (id: number): Promise<ProductWithSpecs> => {
    const response = await api.get<ProductWithSpecs>(`/products/${id}`)
    return response.data
  },

  // Size operations
  listSizes: async (productId: number): Promise<ProductSize[]> => {
    const response = await api.get<ProductSize[]>(`/products/${productId}/sizes`)
    return response.data
  },

  createSize: async (productId: number, data: CreateSizeData): Promise<ProductSize> => {
    const response = await api.post<ProductSize>(`/products/${productId}/sizes`, data)
    return response.data
  },

  updateSize: async (productId: number, sizeId: number, data: UpdateSizeData): Promise<ProductSize> => {
    const response = await api.patch<ProductSize>(`/products/${productId}/sizes/${sizeId}`, data)
    return response.data
  },

  deleteSize: async (productId: number, sizeId: number): Promise<void> => {
    await api.delete(`/products/${productId}/sizes/${sizeId}`)
  },

  // Test specification operations
  listTestSpecs: async (productId: number): Promise<ProductTestSpecification[]> => {
    const response = await api.get<ProductTestSpecification[]>(`/products/${productId}/test-specifications`)
    return response.data
  },

  createTestSpec: async (productId: number, data: CreateTestSpecData): Promise<ProductTestSpecification> => {
    const response = await api.post<ProductTestSpecification>(`/products/${productId}/test-specifications`, data)
    return response.data
  },

  updateTestSpec: async (productId: number, specId: number, data: UpdateTestSpecData): Promise<ProductTestSpecification> => {
    const response = await api.patch<ProductTestSpecification>(`/products/${productId}/test-specifications/${specId}`, data)
    return response.data
  },

  deleteTestSpec: async (productId: number, specId: number): Promise<void> => {
    await api.delete(`/products/${productId}/test-specifications/${specId}`)
  },

  bulkImport: async (rows: BulkImportProductRow[]): Promise<BulkImportResult> => {
    const response = await api.post<BulkImportResult>("/products/bulk-import", rows)
    return response.data
  },
}
