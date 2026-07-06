import { api } from "./client"
import type { LabTestAlias, LabTestAliasList, LabTestBuiltinAliasList } from "@/types"

export interface LabTestAliasFilters {
  page?: number
  page_size?: number
  status?: "pending" | "approved" | "disabled"
  search?: string
  lab_name?: string
}

export interface UpdateLabTestAliasData {
  raw_phrase?: string
  lab_name?: string | null
  lab_test_type_id?: number
}

export const labTestAliasesApi = {
  list: async (filters: LabTestAliasFilters = {}): Promise<LabTestAliasList> => {
    const params = new URLSearchParams()
    if (filters.page) params.append("page", filters.page.toString())
    if (filters.page_size) params.append("page_size", filters.page_size.toString())
    if (filters.status) params.append("status", filters.status)
    if (filters.search) params.append("search", filters.search)
    if (filters.lab_name !== undefined) params.append("lab_name", filters.lab_name)

    const response = await api.get<LabTestAliasList>(`/lab-test-aliases?${params}`)
    return response.data
  },

  listBuiltins: async (): Promise<LabTestBuiltinAliasList> => {
    const response = await api.get<LabTestBuiltinAliasList>("/lab-test-aliases/builtins")
    return response.data
  },

  update: async (id: number, data: UpdateLabTestAliasData): Promise<LabTestAlias> => {
    const response = await api.patch<LabTestAlias>(`/lab-test-aliases/${id}`, data)
    return response.data
  },

  approve: async (id: number): Promise<LabTestAlias> => {
    const response = await api.post<LabTestAlias>(`/lab-test-aliases/${id}/approve`)
    return response.data
  },

  disable: async (id: number, reason?: string): Promise<LabTestAlias> => {
    const response = await api.delete<LabTestAlias>(`/lab-test-aliases/${id}`, {
      data: { reason: reason || null },
    })
    return response.data
  },
}
