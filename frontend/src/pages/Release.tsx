import { useState, useRef } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { ArrowLeft, Loader2, AlertCircle, GripVertical } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { SourcePDFViewer } from "@/components/domain/SourcePDFViewer"
import { COAPreview } from "@/components/domain/COAPreview"
import { ReleaseActions } from "@/components/domain/ReleaseActions"
import {
  useReleaseDetails,
  useReleaseQueue,
  useSaveDraft,
  useApproveRelease,
} from "@/hooks/useRelease"
import type { SaveDraftData } from "@/types/release"

export function ReleasePage() {
  const { lotId: lotIdParam, productId: productIdParam } = useParams<{
    lotId: string
    productId: string
  }>()
  const navigate = useNavigate()
  const lotId = Number(lotIdParam)
  const productId = Number(productIdParam)

  const { data: release, isLoading, error } = useReleaseDetails(lotId, productId)
  const { data: queue = [] } = useReleaseQueue()
  const saveDraft = useSaveDraft()
  const approveRelease = useApproveRelease()

  // Resizable panel state
  const [leftPanelWidth, setLeftPanelWidth] = useState(50) // percentage of left two panes
  const containerRef = useRef<HTMLDivElement>(null)

  // Drag handler for resizable separator
  const handleSeparatorMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = leftPanelWidth
    const containerWidth = containerRef.current?.offsetWidth ?? 0

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const delta = moveEvent.clientX - startX
      const newWidth = startWidth + (delta / containerWidth) * 100
      setLeftPanelWidth(Math.min(Math.max(newWidth, 20), 80)) // clamp 20-80%
    }

    const handleMouseUp = () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }

    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    document.addEventListener("mousemove", handleMouseMove)
    document.addEventListener("mouseup", handleMouseUp)
  }

  const handleSaveDraft = (data: SaveDraftData) => {
    saveDraft.mutate({ lotId, productId, data })
  }

  const handleApprove = async (customerId?: number, notes?: string) => {
    await approveRelease.mutateAsync({ lotId, productId, customerId, notes })

    // Find next pending item in queue or go to dashboard
    const pendingItems = queue.filter(
      (item) => !(item.lot_id === lotId && item.product_id === productId)
    )

    if (pendingItems.length > 0) {
      navigate(`/release/${pendingItems[0].lot_id}/${pendingItems[0].product_id}`)
    } else {
      navigate("/")
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-120px)]">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    )
  }

  if (error || !release) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-120px)]">
        <div className="rounded-xl bg-red-50 p-4">
          <AlertCircle className="h-8 w-8 text-red-400" />
        </div>
        <p className="mt-4 text-[14px] font-medium text-slate-600">
          Failed to load release
        </p>
        <p className="mt-1 text-[13px] text-slate-500">
          The release may not exist or you may not have access
        </p>
        <Button asChild variant="outline" className="mt-4">
          <Link to="/release">Back to Queue</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="sm">
            <Link to="/release">
              <ArrowLeft className="h-4 w-4" />
              Back to Queue
            </Link>
          </Button>
          <div className="h-6 w-px bg-slate-200" />
          <div>
            <h1 className="text-[18px] font-bold text-slate-900 tracking-tight">
              Release COA: {release.lot.reference_number}
            </h1>
          </div>
        </div>
        <Badge
          variant={release.status === "released" ? "emerald" : "amber"}
          className="text-[11px]"
        >
          {release.status === "released" ? "Released" : "Awaiting Release"}
        </Badge>
      </div>

      {/* 3-Column Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left two columns (resizable) */}
        <div ref={containerRef} className="flex flex-1 min-w-0">
          {/* Left Column: Source Documents */}
          <div
            className="flex flex-col min-w-0 overflow-hidden"
            style={{ width: `${leftPanelWidth}%` }}
          >
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/50">
              <h2 className="text-[13px] font-semibold text-slate-700">
                Source Documents
              </h2>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {release.source_pdfs.length} PDF{release.source_pdfs.length !== 1 ? "s" : ""} uploaded
              </p>
            </div>
            <div className="flex-1 overflow-y-auto p-4 bg-slate-50/30">
              <SourcePDFViewer
                lotId={lotId}
                productId={productId}
                sourcePdfs={release.source_pdfs}
              />
            </div>
          </div>

          {/* Draggable Separator */}
          <div
            className="w-2 bg-slate-200 hover:bg-blue-400 cursor-col-resize transition-colors shrink-0 active:bg-blue-500 flex items-center justify-center group"
            onMouseDown={handleSeparatorMouseDown}
          >
            <GripVertical className="h-6 w-3 text-slate-400 group-hover:text-white transition-colors" />
          </div>

          {/* Center Column: Generated COA */}
          <div
            className="flex flex-col min-w-0 overflow-hidden"
            style={{ width: `${100 - leftPanelWidth}%` }}
          >
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/50">
              <h2 className="text-[13px] font-semibold text-slate-700">
                Generated COA
              </h2>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Certificate of Analysis preview
              </p>
            </div>
            <div className="flex-1 overflow-hidden">
              <COAPreview lotId={lotId} productId={productId} />
            </div>
          </div>
        </div>

        {/* Right Column: Release Actions */}
        <div className="w-[224px] border-l border-slate-200 flex flex-col shrink-0">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/50">
            <h2 className="text-[13px] font-semibold text-slate-700">
              Release Actions
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <ReleaseActions
              release={release}
              lotId={lotId}
              productId={productId}
              onSaveDraft={handleSaveDraft}
              onApprove={handleApprove}
              isSaving={saveDraft.isPending}
              isApproving={approveRelease.isPending}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
