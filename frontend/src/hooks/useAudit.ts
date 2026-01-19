import { useQuery } from "@tanstack/react-query"
import { auditApi } from "@/api/audit"

export const auditKeys = {
  all: ["audit"] as const,
  record: (tableName: string, recordId: number) =>
    [...auditKeys.all, "record", tableName, recordId] as const,
  lot: (lotId: number) => [...auditKeys.all, "lot", lotId] as const,
}

/** Get audit history for a specific record */
export function useRecordAuditHistory(
  tableName: string,
  recordId: number,
  skip: number = 0,
  limit: number = 100
) {
  return useQuery({
    queryKey: auditKeys.record(tableName, recordId),
    queryFn: () => auditApi.getRecordHistory(tableName, recordId, skip, limit),
    enabled: !!tableName && recordId > 0,
  })
}

/** Get complete audit history for a lot including all related records */
export function useLotAuditHistory(lotId: number, skip: number = 0, limit: number = 200) {
  return useQuery({
    queryKey: auditKeys.lot(lotId),
    queryFn: () => auditApi.getLotAuditHistory(lotId, skip, limit),
    enabled: lotId > 0,
  })
}
