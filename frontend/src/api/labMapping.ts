import { api } from "./client"
import type { DaaneTestMappingListResponse } from "@/types"

export const labMappingApi = {
  get: async (): Promise<DaaneTestMappingListResponse> => {
    const response = await api.get<DaaneTestMappingListResponse>("/settings/lab-mapping")
    return response.data
  },

  rebuild: async (): Promise<DaaneTestMappingListResponse> => {
    const response = await api.post<DaaneTestMappingListResponse>("/settings/lab-mapping/rebuild")
    return response.data
  },
}
