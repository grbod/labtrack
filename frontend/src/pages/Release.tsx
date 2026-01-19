import { useState, useRef, useEffect } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { motion } from "framer-motion"
import { toast } from "sonner"
import { ArrowLeft, Loader2, AlertCircle, GripVertical, Keyboard } from "lucide-react"
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
  const pdfPaneRef = useRef<HTMLDivElement>(null)
  const coaPaneRef = useRef<HTMLDivElement>(null)

  // Find current position in queue for keyboard navigation
  const currentIndex = queue.findIndex(
    (item) => item.lot_id === lotId && item.product_id === productId
  )
  const prevItem = currentIndex > 0 ? queue[currentIndex - 1] : null
  const nextItem = currentIndex < queue.length - 1 ? queue[currentIndex + 1] : null

  // Keyboard navigation: Escape to go back, left/right arrows to navigate queue
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't navigate if user is typing in an input/textarea
      const activeEl = document.activeElement as HTMLElement
      if (
        activeEl?.tagName === "INPUT" ||
        activeEl?.tagName === "TEXTAREA" ||
        activeEl?.isContentEditable
      ) {
        return
      }

      if (e.key === "Escape") {
        navigate("/release")
      } else if (e.shiftKey && e.key === "ArrowLeft") {
        // Shift+Left: shrink PDF pane
        e.preventDefault()
        setLeftPanelWidth((prev) => Math.max(20, prev - 5))
      } else if (e.shiftKey && e.key === "ArrowRight") {
        // Shift+Right: expand PDF pane
        e.preventDefault()
        setLeftPanelWidth((prev) => Math.min(80, prev + 5))
      } else if (e.shiftKey && e.altKey && e.key === "ArrowDown") {
        // Shift+Alt+Down: scroll COA Preview pane down
        e.preventDefault()
        coaPaneRef.current?.scrollBy({ top: 150, behavior: 'smooth' })
      } else if (e.shiftKey && e.altKey && e.key === "ArrowUp") {
        // Shift+Alt+Up: scroll COA Preview pane up
        e.preventDefault()
        coaPaneRef.current?.scrollBy({ top: -150, behavior: 'smooth' })
      } else if (e.shiftKey && e.key === "ArrowDown") {
        // Shift+Down: scroll PDF pane down
        e.preventDefault()
        pdfPaneRef.current?.scrollBy({ top: 150, behavior: 'smooth' })
      } else if (e.shiftKey && e.key === "ArrowUp") {
        // Shift+Up: scroll PDF pane up
        e.preventDefault()
        pdfPaneRef.current?.scrollBy({ top: -150, behavior: 'smooth' })
      } else if (e.key === "ArrowLeft" && prevItem) {
        e.preventDefault()
        navigate(`/release/${prevItem.lot_id}/${prevItem.product_id}`)
      } else if (e.key === "ArrowRight" && nextItem) {
        e.preventDefault()
        navigate(`/release/${nextItem.lot_id}/${nextItem.product_id}`)
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [navigate, prevItem, nextItem, leftPanelWidth])

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
    // Success popup in ReleaseActions handles navigation
  }

  const handleDone = () => {
    navigate("/release")
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
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.275 }}
      className="flex flex-col h-[calc(100vh-64px)]"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-2 border-b border-slate-200 bg-white shrink-0">
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
        <div className="flex items-center gap-3">
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
                    <span className="text-slate-500">Scroll PDF</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">Shift + ↑↓</kbd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Scroll COA</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">Shift + Alt + ↑↓</kbd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Resize panes</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">Shift + ←→</kbd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Navigate queue</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">←→</kbd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Back to queue</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">Esc</kbd>
                  </div>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <Badge
            variant={release.status === "released" ? "emerald" : "amber"}
            className="text-[11px]"
          >
            {release.status === "released" ? "Released" : "Awaiting Release"}
          </Badge>
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
              onDone={handleDone}
              isSaving={saveDraft.isPending}
              isApproving={approveRelease.isPending}
            />
          </div>
        </div>
      </div>
    </motion.div>
  )
}
