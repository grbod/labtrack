import { api } from "./client"
import type { LabTestType, LabTestTypeCategoryCount, PaginatedResponse } from "@/types"

export interface LabTestTypeFilters {
  page?: number
  page_size?: number
  search?: string
  category?: string
  is_active?: boolean
}

export interface CreateLabTestTypeData {
  test_name: string
  test_category: string
  default_unit?: string
  description?: string
  test_method?: string
  abbreviations?: string
  default_specification?: string
}

export interface UpdateLabTestTypeData extends Partial<CreateLabTestTypeData> {
  is_active?: boolean
}

export interface BulkImportLabTestTypeRow {
  test_name: string
  test_category: string
  default_unit?: string
  description?: string
  test_method?: string
  abbreviations?: string
  default_specification?: string
}

export interface BulkImportResult {
  total_rows: number
  imported: number
  skipped: number
  errors: string[]
}

export const labTestTypesApi = {
  list: async (filters: LabTestTypeFilters = {}): Promise<PaginatedResponse<LabTestType>> => {
    const params = new URLSearchParams()
    if (filters.page) params.append("page", filters.page.toString())
    if (filters.page_size) params.append("page_size", filters.page_size.toString())
    if (filters.search) params.append("search", filters.search)
    if (filters.category) params.append("category", filters.category)
    if (filters.is_active !== undefined) params.append("is_active", filters.is_active.toString())

    const response = await api.get<PaginatedResponse<LabTestType>>(`/lab-test-types?${params}`)
    return response.data
  },

  get: async (id: number): Promise<LabTestType> => {
    const response = await api.get<LabTestType>(`/lab-test-types/${id}`)
    return response.data
  },

  getCategories: async (): Promise<LabTestTypeCategoryCount[]> => {
    const response = await api.get<LabTestTypeCategoryCount[]>("/lab-test-types/categories")
    return response.data
  },

  create: async (data: CreateLabTestTypeData): Promise<LabTestType> => {
    const response = await api.post<LabTestType>("/lab-test-types", data)
    return response.data
  },

  update: async (id: number, data: UpdateLabTestTypeData): Promise<LabTestType> => {
    const response = await api.patch<LabTestType>(`/lab-test-types/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/lab-test-types/${id}`)
  },

  bulkImport: async (rows: BulkImportLabTestTypeRow[]): Promise<BulkImportResult> => {
    const response = await api.post<BulkImportResult>("/lab-test-types/bulk-import", rows)
    return response.data
  },
}
