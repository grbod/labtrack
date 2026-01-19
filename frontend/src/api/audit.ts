import { api } from "./client"
import type { AuditHistoryResponse, LotAuditHistoryResponse } from "@/types"

export const auditApi = {
  /** Get audit history for a specific record */
  getRecordHistory: async (
    tableName: string,
    recordId: number,
    skip: number = 0,
    limit: number = 100
  ): Promise<AuditHistoryResponse> => {
    const params = new URLSearchParams()
    if (skip > 0) params.append("skip", skip.toString())
    if (limit !== 100) params.append("limit", limit.toString())

    const response = await api.get<AuditHistoryResponse>(
      `/audit/${tableName}/${recordId}?${params}`
    )
    return response.data
  },

  /** Get complete audit history for a lot including related records */
  getLotAuditHistory: async (
    lotId: number,
    skip: number = 0,
    limit: number = 200
  ): Promise<LotAuditHistoryResponse> => {
    const params = new URLSearchParams()
    if (skip > 0) params.append("skip", skip.toString())
    if (limit !== 200) params.append("limit", limit.toString())

    const response = await api.get<LotAuditHistoryResponse>(
      `/audit/lots/${lotId}/complete?${params}`
    )
    return response.data
  },
}
