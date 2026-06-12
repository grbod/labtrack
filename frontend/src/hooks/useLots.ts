import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { lotsApi, type LotFilters, type ArchivedLotFilters, type CreateLotData, type UpdateLotData, type SublotData } from "@/api/lots"
import { releaseKeys } from "@/hooks/useRelease"
import { extractApiErrorMessage } from "@/lib/api-utils"
import type { LotStatusRecalculationResponse, LotStatus } from "@/types"

export const lotKeys = {
  all: ["lots"] as const,
  lists: () => [...lotKeys.all, "list"] as const,
  list: (filters: LotFilters) => [...lotKeys.lists(), filters] as const,
  details: () => [...lotKeys.all, "detail"] as const,
  detail: (id: number) => [...lotKeys.details(), id] as const,
  detailWithSpecs: (id: number) => [...lotKeys.details(), id, "with-specs"] as const,
  statusCounts: () => [...lotKeys.all, "statusCounts"] as const,
  sublots: (lotId: number) => [...lotKeys.all, "sublots", lotId] as const,
  archived: () => [...lotKeys.all, "archived"] as const,
  archivedList: (filters: ArchivedLotFilters) => [...lotKeys.archived(), filters] as const,
}

export function useLots(filters: LotFilters = {}) {
  return useQuery({
    queryKey: lotKeys.list(filters),
    queryFn: () => lotsApi.list(filters),
  })
}

export function useLot(id: number) {
  return useQuery({
    queryKey: lotKeys.detail(id),
    queryFn: () => lotsApi.get(id),
    enabled: !!id,
  })
}

/** Fetch lot with products and their test specifications (for Sample Modal) */
export function useLotWithSpecs(id: number) {
  return useQuery({
    queryKey: lotKeys.detailWithSpecs(id),
    queryFn: () => lotsApi.getWithSpecs(id),
    enabled: id > 0,
  })
}

export function useLotStatusCounts() {
  return useQuery({
    queryKey: lotKeys.statusCounts(),
    queryFn: () => lotsApi.getStatusCounts(),
  })
}

export function useCreateLot() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateLotData) => lotsApi.create(data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to create lot"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
    },
  })
}

export function useUpdateLot() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateLotData }) =>
      lotsApi.update(id, data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update lot"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(variables.id) })
    },
  })
}

export function useUpdateLotStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      status,
      rejectionReason,
      overrideReason,
    }: {
      id: number
      status: LotStatus
      rejectionReason?: string
      overrideReason?: string
    }) => lotsApi.updateStatus(id, status, rejectionReason, overrideReason),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update lot status"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.detailWithSpecs(variables.id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
      // Invalidate release queue when status changes (e.g., approved → shows in release queue)
      queryClient.invalidateQueries({ queryKey: releaseKeys.queue() })
      // Invalidate archived lots (audit trail) when status changes to released/rejected
      queryClient.invalidateQueries({ queryKey: lotKeys.archived() })
    },
  })
}

export function useSubmitForReview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      overrideUserId,
      returnResponseNote,
    }: {
      id: number
      overrideUserId?: number
      returnResponseNote?: string
    }) => lotsApi.submitForReview(id, { overrideUserId, returnResponseNote }),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to submit lot for review"))
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.detailWithSpecs(id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
      // Invalidate release queue so it auto-refreshes when navigating there
      queryClient.invalidateQueries({ queryKey: releaseKeys.queue() })
    },
  })
}

export function useRecalculateLotStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => lotsApi.recalculateStatus(id),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to recalculate lot status"))
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.detailWithSpecs(id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
      queryClient.invalidateQueries({ queryKey: releaseKeys.queue() })
    },
  })
}

export function usePreviewStatusRecalculation() {
  return useMutation<LotStatusRecalculationResponse, unknown, void>({
    mutationFn: () => lotsApi.previewStatusRecalculation(),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to preview status recalculation"))
    },
  })
}

export function useApplyStatusRecalculation() {
  const queryClient = useQueryClient()

  return useMutation<LotStatusRecalculationResponse, unknown, void>({
    mutationFn: () => lotsApi.applyStatusRecalculation(),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to apply status recalculation"))
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.details() })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
      queryClient.invalidateQueries({ queryKey: releaseKeys.queue() })
      toast.success(`Updated ${result.changed_count} sample${result.changed_count === 1 ? "" : "s"}`)
    },
  })
}

export function useReturnLotForReview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ lotId, reason }: { lotId: number; reason: string }) =>
      lotsApi.returnForReview(lotId, reason),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to return lot for review"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(variables.lotId) })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
      queryClient.invalidateQueries({ queryKey: releaseKeys.queue() })
    },
  })
}

export function useRejectLot() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ lotId, reason }: { lotId: number; reason: string }) =>
      lotsApi.updateStatus(lotId, "rejected", reason),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to reject lot"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(variables.lotId) })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
      queryClient.invalidateQueries({ queryKey: releaseKeys.queue() })
    },
  })
}

export function useResubmitLot() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => lotsApi.resubmit(id),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to resubmit lot"))
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
    },
  })
}

export function useDeleteLot() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => lotsApi.delete(id),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to delete lot"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
    },
  })
}

// Sublot hooks
export function useSublots(lotId: number) {
  return useQuery({
    queryKey: lotKeys.sublots(lotId),
    queryFn: () => lotsApi.listSublots(lotId),
    enabled: !!lotId,
  })
}

export function useCreateSublotsBulk() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ lotId, sublots }: { lotId: number; sublots: SublotData[] }) =>
      lotsApi.createSublotsBulk(lotId, sublots),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to bulk create sublots"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.sublots(variables.lotId) })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(variables.lotId) })
    },
  })
}

/** Fetch archived (completed) lots for historical view */
export function useArchivedLots(filters: ArchivedLotFilters = {}, enabled: boolean = true) {
  return useQuery({
    queryKey: lotKeys.archivedList(filters),
    queryFn: () => lotsApi.listArchived(filters),
    enabled,
  })
}
