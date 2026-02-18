import { useMutation } from "@tanstack/react-query"
import { daaneCocApi } from "@/api/daaneCoc"
import { downloadBlob } from "@/lib/utils"

export function useDownloadLotDaaneCoc() {
  return useMutation({
    mutationFn: (lotId: number) => daaneCocApi.downloadLotCoc(lotId),
    onSuccess: ({ blob, filename }) => {
      downloadBlob(blob, filename)
    },
  })
}

export function useDownloadLotDaaneCocPdf() {
  return useMutation({
    mutationFn: ({
      lotId,
      selectedLabTestTypeIds,
      specialInstructions,
    }: {
      lotId: number
      selectedLabTestTypeIds?: number[]
      specialInstructions?: string
    }) => daaneCocApi.downloadLotCocPdf(lotId, selectedLabTestTypeIds, specialInstructions),
    onSuccess: ({ blob, filename }) => {
      downloadBlob(blob, filename)
    },
  })
}

export function useDownloadRetestDaaneCoc() {
  return useMutation({
    mutationFn: (requestId: number) => daaneCocApi.downloadRetestCoc(requestId),
    onSuccess: ({ blob, filename }) => {
      downloadBlob(blob, filename)
    },
  })
}

export function useDownloadRetestDaaneCocPdf() {
  return useMutation({
    mutationFn: ({
      requestId,
      specialInstructions,
    }: {
      requestId: number
      specialInstructions?: string
    }) => daaneCocApi.downloadRetestCocPdf(requestId, specialInstructions),
    onSuccess: ({ blob, filename }) => {
      downloadBlob(blob, filename)
    },
  })
}
