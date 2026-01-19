import { api } from "./client"
import type { COACategoryOrder } from "@/types"

export interface UpdateCOACategoryOrderData {
  category_order: string[]
}

export const coaCategoryOrderApi = {
  get: async (): Promise<COACategoryOrder> => {
    const response = await api.get<COACategoryOrder>("/settings/coa-category-order")
    return response.data
  },

  update: async (data: UpdateCOACategoryOrderData): Promise<COACategoryOrder> => {
    const response = await api.put<COACategoryOrder>("/settings/coa-category-order", data)
    return response.data
  },

  reset: async (): Promise<COACategoryOrder> => {
    const response = await api.post<COACategoryOrder>("/settings/coa-category-order/reset")
    return response.data
  },

  getActiveCategories: async (): Promise<string[]> => {
    const response = await api.get<string[]>("/settings/coa-category-order/active-categories")
    return response.data
  },
}
