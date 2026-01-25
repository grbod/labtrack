import { useState, useRef, useEffect, useCallback } from "react"
import { useParams, Link, useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { ArrowLeft, Loader2, AlertCircle, GripVertical, Archive, Keyboard } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { SourcePDFViewer } from "@/components/domain/SourcePDFViewer"
import { COAPreview } from "@/components/domain/COAPreview"
import { ArchiveLotActions } from "@/components/domain/ArchiveLotActions"
import { useReleaseDetails } from "@/hooks/useRelease"
import { useLot } from "@/hooks/useLots"

export function ArchiveLotPage() {
  const { lotId: lotIdParam, productId: productIdParam } = useParams<{
    lotId: string
    productId: string
  }>()
  const lotId = Number(lotIdParam)
  const productId = Number(productIdParam)
  const navigate = useNavigate()

  const { data: release, isLoading, error } = useReleaseDetails(lotId, productId)
  const { data: lot } = useLot(lotId)

  // Modal state - lifted from ArchiveLotActions so ESC handler can check it
  const [showAuditModal, setShowAuditModal] = useState(false)

  // Exit animation state
  const [isExiting, setIsExiting] = useState(false)

  const handleExit = useCallback(() => {
    setIsExiting(true)
    setTimeout(() => navigate("/audittrail"), 200)
  }, [navigate])

  // Keyboard shortcuts: ESC to go back, A to open audit modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Let modal handle its own ESC when open
      if (showAuditModal) {
        return
      }

      // Skip if typing in an input
      const activeEl = document.activeElement as HTMLElement
      if (activeEl?.tagName === "INPUT" || activeEl?.tagName === "TEXTAREA") {
        return
      }

      if (e.key === "Escape") {
        handleExit()
      } else if (e.key === "a" || e.key === "A") {
        e.preventDefault()
        setShowAuditModal(true)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [handleExit, showAuditModal])

  // Resizable panel state
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const containerRef = useRef<HTMLDivElement>(null)
  const pdfPaneRef = useRef<HTMLDivElement>(null)
  const coaPaneRef = useRef<HTMLDivElement>(null)

  // Drag handler for resizable separator
  const handleSeparatorMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = leftPanelWidth
    const containerWidth = containerRef.current?.offsetWidth ?? 0

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const delta = moveEvent.clientX - startX
      const newWidth = startWidth + (delta / containerWidth) * 100
      setLeftPanelWidth(Math.min(Math.max(newWidth, 20), 80))
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
          Failed to load archived sample
        </p>
        <p className="mt-1 text-[13px] text-slate-500">
          The sample may not exist or you may not have access
        </p>
        <Button asChild variant="outline" className="mt-4">
          <Link to="/audittrail">Back to Audit Trail</Link>
        </Button>
      </div>
    )
  }

  const isReleased = release.status === "released"

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: isExiting ? 0 : 1 }}
      transition={{ duration: isExiting ? 0.2 : 0.275 }}
      className="flex flex-col h-[calc(100vh-64px)]"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-2 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={handleExit}>
            <ArrowLeft className="h-4 w-4" />
            Back to Audit Trail
          </Button>
          <div className="h-6 w-px bg-slate-200" />
          <div className="flex items-center gap-2">
            <Archive className="h-4 w-4 text-slate-400" />
            <h1 className="text-[18px] font-bold text-slate-900 tracking-tight">
              {release.lot.reference_number}
            </h1>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            variant={isReleased ? "emerald" : "destructive"}
            className="text-[11px]"
          >
            {isReleased ? "Released" : "Rejected"}
          </Badge>
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="text-slate-400 hover:text-slate-600 transition-colors">
                  <Keyboard className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-[12px]">
                <div className="space-y-1">
                  <div className="font-medium text-slate-700 mb-1.5">Keyboard Shortcuts</div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">View Audit Trail</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">A</kbd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Back to list</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">Esc</kbd>
                  </div>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
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
            <div className="px-3 py-1.5 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
              <h2 className="text-[13px] font-semibold text-slate-700">
                Source Documents
              </h2>
              <span className="text-[11px] text-slate-500">
                {release.source_pdfs.length} PDF{release.source_pdfs.length !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="flex-1 overflow-hidden p-1 bg-slate-50/30">
              <SourcePDFViewer
                lotId={lotId}
                productId={productId}
                sourcePdfs={release.source_pdfs}
                scrollRef={pdfPaneRef}
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
            <div className="flex-1 overflow-hidden">
              <COAPreview lotId={lotId} productId={productId} scrollRef={coaPaneRef} />
            </div>
          </div>
        </div>

        {/* Right Column: Archive Actions */}
        <div className="w-[224px] border-l border-slate-200 flex flex-col shrink-0">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/50">
            <h2 className="text-[13px] font-semibold text-slate-700">
              Archive Details
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <ArchiveLotActions
              release={release}
              lotId={lotId}
              productId={productId}
              rejectionReason={lot?.rejection_reason}
              showAuditModal={showAuditModal}
              onShowAuditModal={setShowAuditModal}
            />
          </div>
        </div>
      </div>
    </motion.div>
  )
}
