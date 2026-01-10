import { useState, useRef, useEffect, useCallback } from "react"
import { toast } from "sonner"
import { Loader2, FileText, ZoomIn, ZoomOut, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { usePreviewData, useSaveDraft, releaseKeys } from "@/hooks/useRelease"
import { useQueryClient } from "@tanstack/react-query"
import { COAPreviewDocument } from "./COAPreviewDocument"

// Base document dimensions at 96 DPI
const DOCUMENT_BASE_WIDTH = 8.5 * 96 // 816px
const DOCUMENT_BASE_HEIGHT = 11 * 96 // 1056px

interface COAPreviewProps {
  lotId: number
  productId: number
  isGenerating?: boolean
  hasError?: boolean
  scrollRef?: React.RefObject<HTMLDivElement>
}

export function COAPreview({ lotId, productId, isGenerating, hasError, scrollRef }: COAPreviewProps) {
  const [zoom, setZoom] = useState(100)
  const [containerWidth, setContainerWidth] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  // Combine internal ref with external scrollRef
  const setRefs = useCallback((node: HTMLDivElement | null) => {
    containerRef.current = node
    if (scrollRef && 'current' in scrollRef) {
      (scrollRef as React.MutableRefObject<HTMLDivElement | null>).current = node
    }
  }, [scrollRef])

  const { data: previewData, isLoading, error } = usePreviewData(lotId, productId)
  const saveDraft = useSaveDraft()

  // Measure container width on mount and resize
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const measure = () => {
      // Subtract padding (p-1 = 4px each side = 8px total)
      setContainerWidth(container.clientWidth - 8)
    }
    measure()

    const observer = new ResizeObserver(measure)
    observer.observe(container)
    return () => observer.disconnect()
  }, [previewData]) // Re-run when previewData loads (ref becomes available)

  // Calculate scale: fit-to-width as base, then apply zoom multiplier
  const fitScale = containerWidth > 0 ? containerWidth / DOCUMENT_BASE_WIDTH : 1
  const finalScale = fitScale * (zoom / 100)

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 25, 200))
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 25, 50))
  const handleResetZoom = () => setZoom(100)

  const handleNotesChange = (notes: string) => {
    saveDraft.mutate(
      { lotId, productId, data: { notes } },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: releaseKeys.previewData(lotId, productId) })
          toast.success("Notes saved")
        },
        onError: () => {
          toast.error("Failed to save notes")
        },
      }
    )
  }

  const handleMfgDateChange = (date: Date | null) => {
    saveDraft.mutate(
      { lotId, productId, data: { mfg_date: date ? date.toISOString() : null } },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: releaseKeys.previewData(lotId, productId) })
          queryClient.invalidateQueries({ queryKey: releaseKeys.detail(lotId, productId) })
          toast.success("Manufacturing date saved")
        },
        onError: () => {
          toast.error("Failed to save manufacturing date")
        },
      }
    )
  }

  const handleExpDateChange = (date: Date | null) => {
    saveDraft.mutate(
      { lotId, productId, data: { exp_date: date ? date.toISOString() : null } },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: releaseKeys.previewData(lotId, productId) })
          queryClient.invalidateQueries({ queryKey: releaseKeys.detail(lotId, productId) })
          toast.success("Expiration date saved")
        },
        onError: () => {
          toast.error("Failed to save expiration date")
        },
      }
    )
  }

  if (isGenerating || isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        <p className="mt-4 text-[14px] font-medium text-slate-600">
          {isGenerating ? "Generating COA..." : "Loading preview..."}
        </p>
        <p className="mt-1 text-[13px] text-slate-500">This may take a few moments</p>
      </div>
    )
  }

  if (hasError || error || !previewData) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16">
        <div className="rounded-xl bg-red-50 p-4">
          <FileText className="h-8 w-8 text-red-400" />
        </div>
        <p className="mt-4 text-[14px] font-medium text-slate-600">Failed to load COA preview</p>
        <p className="mt-1 text-[13px] text-slate-500">Please try again or contact support</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header with Title and Zoom Controls */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-slate-200 bg-slate-50/50 shrink-0">
        <h2 className="text-[13px] font-semibold text-slate-700">
          COA Preview
        </h2>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={handleZoomOut}
            disabled={zoom <= 50}
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="text-[11px] font-medium text-slate-500 w-10 text-center">
            {zoom}%
          </span>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={handleZoomIn}
            disabled={zoom >= 200}
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={handleResetZoom}
            disabled={zoom === 100}
            title="Reset zoom"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* WYSIWYG Preview */}
      <div ref={setRefs} className="flex-1 overflow-auto bg-slate-100 p-1">
        <div
          style={{
            // Set width to scaled document width so it centers properly
            width: DOCUMENT_BASE_WIDTH * finalScale,
            // Reserve height for the scaled document to prevent clipping
            minHeight: DOCUMENT_BASE_HEIGHT * finalScale,
            margin: "0 auto", // Center the document
          }}
        >
          <COAPreviewDocument
            data={previewData}
            scale={finalScale}
            onNotesChange={handleNotesChange}
            onMfgDateChange={handleMfgDateChange}
            onExpDateChange={handleExpDateChange}
          />
        </div>
      </div>
    </div>
  )
}
