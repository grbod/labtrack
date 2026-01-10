import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { releaseApi, customerApi } from "@/api/release"
import type { ArchiveFilters, SaveDraftData, CreateCustomerData } from "@/types/release"

export const releaseKeys = {
  all: ["releases"] as const,
  queue: () => [...releaseKeys.all, "queue"] as const,
  details: () => [...releaseKeys.all, "detail"] as const,
  detail: (lotId: number, productId: number) =>
    [...releaseKeys.details(), lotId, productId] as const,
  previewData: (lotId: number, productId: number) =>
    [...releaseKeys.all, "preview-data", lotId, productId] as const,
  emailHistory: (lotId: number, productId: number) =>
    [...releaseKeys.all, "emails", lotId, productId] as const,
  archive: (filters: ArchiveFilters) => [...releaseKeys.all, "archive", filters] as const,
}

export const customerKeys = {
  all: ["customers"] as const,
  list: () => [...customerKeys.all, "list"] as const,
}

/** Fetch release queue items (Lot+Product based) */
export function useReleaseQueue() {
  return useQuery({
    queryKey: releaseKeys.queue(),
    queryFn: () => releaseApi.getQueue(),
  })
}

/** Fetch release details for a Lot+Product combination */
export function useReleaseDetails(lotId: number, productId: number) {
  return useQuery({
    queryKey: releaseKeys.detail(lotId, productId),
    queryFn: () => releaseApi.getDetails(lotId, productId),
    enabled: lotId > 0 && productId > 0,
  })
}

/** Fetch COA preview data for frontend rendering */
export function usePreviewData(lotId: number, productId: number) {
  return useQuery({
    queryKey: releaseKeys.previewData(lotId, productId),
    queryFn: () => releaseApi.getPreviewData(lotId, productId),
    enabled: lotId > 0 && productId > 0,
  })
}

/** Fetch email history for a lot/product */
export function useEmailHistory(lotId: number, productId: number) {
  return useQuery({
    queryKey: releaseKeys.emailHistory(lotId, productId),
    queryFn: () => releaseApi.getEmailHistory(lotId, productId),
    enabled: lotId > 0 && productId > 0,
  })
}

/** Search archived releases */
export function useArchive(filters: ArchiveFilters = {}) {
  return useQuery({
    queryKey: releaseKeys.archive(filters),
    queryFn: () => releaseApi.searchArchive(filters),
  })
}

/** Save draft mutation for lot/product */
export function useSaveDraft() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      lotId,
      productId,
      data,
    }: {
      lotId: number
      productId: number
      data: SaveDraftData
    }) => releaseApi.saveDraft(lotId, productId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: releaseKeys.detail(variables.lotId, variables.productId),
      })
    },
  })
}

/** Approve release mutation for lot/product */
export function useApproveRelease() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      lotId,
      productId,
      customerId,
      notes,
    }: {
      lotId: number
      productId: number
      customerId?: number
      notes?: string
    }) => releaseApi.approve(lotId, productId, customerId, notes),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: releaseKeys.queue() })
      queryClient.invalidateQueries({
        queryKey: releaseKeys.detail(variables.lotId, variables.productId),
      })
    },
  })
}

/** Send email mutation for lot/product */
export function useSendEmail() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      lotId,
      productId,
      recipientEmail,
    }: {
      lotId: number
      productId: number
      recipientEmail: string
    }) => releaseApi.sendEmail(lotId, productId, recipientEmail),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: releaseKeys.emailHistory(variables.lotId, variables.productId),
      })
    },
  })
}

/** Fetch all customers */
export function useCustomers() {
  return useQuery({
    queryKey: customerKeys.list(),
    queryFn: () => customerApi.list(),
  })
}

/** Create customer mutation */
export function useCreateCustomer() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateCustomerData) => customerApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: customerKeys.list() })
    },
  })
}
