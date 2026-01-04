import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { lotsApi, type LotFilters, type CreateLotData, type UpdateLotData, type SublotData } from "@/api/lots"
import type { LotStatus } from "@/types"

export const lotKeys = {
  all: ["lots"] as const,
  lists: () => [...lotKeys.all, "list"] as const,
  list: (filters: LotFilters) => [...lotKeys.lists(), filters] as const,
  details: () => [...lotKeys.all, "detail"] as const,
  detail: (id: number) => [...lotKeys.details(), id] as const,
  detailWithSpecs: (id: number) => [...lotKeys.details(), id, "with-specs"] as const,
  statusCounts: () => [...lotKeys.all, "statusCounts"] as const,
  sublots: (lotId: number) => [...lotKeys.all, "sublots", lotId] as const,
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
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(variables.id) })
    },
  })
}

export function useUpdateLotStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, status, rejectionReason }: { id: number; status: LotStatus; rejectionReason?: string }) =>
      lotsApi.updateStatus(id, status, rejectionReason),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
    },
  })
}

export function useSubmitForReview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => lotsApi.submitForReview(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(id) })
      queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
    },
  })
}

export function useResubmitLot() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => lotsApi.resubmit(id),
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
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: lotKeys.sublots(variables.lotId) })
      queryClient.invalidateQueries({ queryKey: lotKeys.detail(variables.lotId) })
    },
  })
}
