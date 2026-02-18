import { useState, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { releaseApi, customerApi } from "@/api/release"
import { downloadBlob } from "@/lib/utils"
import { toast } from "sonner"
import type { ArchiveFilters, SaveDraftData, CreateCustomerData } from "@/types/release"

export const releaseKeys = {
  all: ["releases"] as const,
  queue: () => [...releaseKeys.all, "queue"] as const,
  recentlyReleased: (days: number) => [...releaseKeys.all, "recently-released", days] as const,
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

/** Fetch recently released COAs within a given number of days */
export function useRecentlyReleased(days: number) {
  return useQuery({
    queryKey: releaseKeys.recentlyReleased(days),
    queryFn: () => releaseApi.getRecentlyReleased(days),
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
      // Invalidate all recently released queries to refresh the list
      queryClient.invalidateQueries({ queryKey: [...releaseKeys.all, "recently-released"] })
      // Invalidate archived lots (audit trail) so it refreshes with new released items
      queryClient.invalidateQueries({ queryKey: ["lots", "archived"] })
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

/** Download COA mutation - fetches PDF blob and triggers download */
export function useDownloadCoa() {
  return useMutation({
    mutationFn: async ({ lotId, productId }: { lotId: number; productId: number }) => {
      const { blob, filename } = await releaseApi.downloadCoaBlob(lotId, productId)
      downloadBlob(blob, filename)
    },
  })
}

/** Download COA with per-item loading state tracking, cursor-wait, and 404 handling */
export function useDownloadWithTracking() {
  const [downloadingItem, setDownloadingItem] = useState<string | null>(null)
  const downloadCoa = useDownloadCoa()

  const handleDownload = useCallback(async (lotId: number, productId: number) => {
    const itemKey = `${lotId}-${productId}`
    setDownloadingItem(itemKey)
    try {
      await downloadCoa.mutateAsync({ lotId, productId })
      toast.success("COA downloaded successfully")
    } catch (error: unknown) {
      console.error("Failed to download COA:", error)
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        toast.error("File not found")
      } else {
        toast.error("Failed to download COA")
      }
    } finally {
      setDownloadingItem(null)
    }
  }, [downloadCoa])

  const isDownloading = useCallback((lotId: number, productId: number) => {
    return downloadingItem === `${lotId}-${productId}`
  }, [downloadingItem])

  return { handleDownload, isDownloading, downloadingItem }
}

/** Regenerate COA PDF mutation - forces fresh PDF generation */
export function useRegenerateCoa() {
  return useMutation({
    mutationFn: async ({ lotId, productId }: { lotId: number; productId: number }) => {
      await releaseApi.regenerateCoa(lotId, productId)
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
