import { useState } from "react"
import { Loader2, FileText, ZoomIn, ZoomOut, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { releaseApi } from "@/api/release"

interface COAPreviewProps {
  lotId: number
  productId: number
  isGenerating?: boolean
  hasError?: boolean
}

export function COAPreview({ lotId, productId, isGenerating, hasError }: COAPreviewProps) {
  const [zoom, setZoom] = useState(100)

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 25, 200))
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 25, 50))
  const handleResetZoom = () => setZoom(100)

  const previewUrl = releaseApi.getPreviewUrl(lotId, productId)

  if (isGenerating) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        <p className="mt-4 text-[14px] font-medium text-slate-600">Generating COA...</p>
        <p className="mt-1 text-[13px] text-slate-500">This may take a few moments</p>
      </div>
    )
  }

  if (hasError) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16">
        <div className="rounded-xl bg-red-50 p-4">
          <FileText className="h-8 w-8 text-red-400" />
        </div>
        <p className="mt-4 text-[14px] font-medium text-slate-600">Failed to generate COA</p>
        <p className="mt-1 text-[13px] text-slate-500">Please try again or contact support</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Zoom Controls */}
      <div className="flex items-center justify-end gap-1 px-3 py-2 border-b border-slate-200 bg-slate-50">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={handleZoomOut}
          disabled={zoom <= 50}
          title="Zoom out"
        >
          <ZoomOut className="h-4 w-4" />
        </Button>
        <span className="text-[12px] font-medium text-slate-600 w-12 text-center">
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

      {/* PDF Preview */}
      <div className="flex-1 overflow-auto bg-slate-100 p-4">
        <div
          className="mx-auto transition-transform duration-200 origin-top"
          style={{ width: `${zoom}%` }}
        >
          <object
            data={previewUrl}
            type="application/pdf"
            className="w-full h-[800px] rounded-lg shadow-sm"
          >
            <div className="flex flex-col items-center justify-center h-[800px] bg-white rounded-lg">
              <FileText className="h-8 w-8 text-slate-400" />
              <p className="mt-2 text-[13px] text-slate-500">Unable to display PDF preview</p>
              <a
                href={previewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 text-[13px] font-medium text-blue-600 hover:text-blue-700"
              >
                Open in new tab
              </a>
            </div>
          </object>
        </div>
      </div>
    </div>
  )
}
