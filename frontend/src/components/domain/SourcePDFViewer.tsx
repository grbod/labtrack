import { useState, useEffect, useCallback, useRef } from "react"
import { Document, Page, pdfjs } from "react-pdf"
import { FileText, Loader2 } from "lucide-react"
import { releaseApi } from "@/api/release"
import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

interface SourcePDFViewerProps {
  lotId: number
  productId: number
  sourcePdfs: string[]
}

interface PdfData {
  filename: string
  url: string
  numPages: number
}

interface LensPosition {
  x: number
  y: number
  visible: boolean
}

const ZOOM_FACTOR = 2.5
const LENS_SIZE = 320

function PdfPage({
  pageNumber,
  width,
  totalPages,
  globalPageNumber,
}: {
  pageNumber: number
  width: number
  totalPages: number
  globalPageNumber: number
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [lens, setLens] = useState<LensPosition>({ x: 0, y: 0, visible: false })
  const [imageData, setImageData] = useState<string | null>(null)
  const [renderedWidth, setRenderedWidth] = useState<number>(width)

  // Capture canvas when page renders
  const onRenderSuccess = useCallback(() => {
    if (containerRef.current) {
      const canvas = containerRef.current.querySelector("canvas")
      if (canvas) {
        setImageData(canvas.toDataURL())
        setRenderedWidth(width)
      }
    }
  }, [width])

  // Reset imageData when width changes significantly
  useEffect(() => {
    if (Math.abs(width - renderedWidth) > 10) {
      setImageData(null)
    }
  }, [width, renderedWidth])

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return

    const rect = containerRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    setLens({ x, y, visible: true })
  }, [])

  const handleMouseLeave = useCallback(() => {
    setLens((prev) => ({ ...prev, visible: false }))
  }, [])

  return (
    <div
      ref={containerRef}
      className="relative cursor-crosshair"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <Page
        pageNumber={pageNumber}
        width={width}
        className="[&>canvas]:!block"
        renderTextLayer={false}
        renderAnnotationLayer={false}
        onRenderSuccess={onRenderSuccess}
      />

      {/* Page number badge */}
      <div className="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded">
        {globalPageNumber} / {totalPages}
      </div>

      {/* Magnifying lens */}
      {lens.visible && imageData && (
        <div
          className="absolute pointer-events-none border-2 border-blue-400 rounded-full overflow-hidden shadow-xl z-10"
          style={{
            width: LENS_SIZE,
            height: LENS_SIZE,
            left: lens.x - LENS_SIZE / 2,
            top: lens.y - LENS_SIZE / 2,
            backgroundImage: `url(${imageData})`,
            backgroundSize: `${renderedWidth * ZOOM_FACTOR}px auto`,
            backgroundPosition: `${-lens.x * ZOOM_FACTOR + LENS_SIZE / 2}px ${-lens.y * ZOOM_FACTOR + LENS_SIZE / 2}px`,
            backgroundRepeat: "no-repeat",
          }}
        >
          {/* Crosshair in center of lens */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-px h-3 bg-blue-400/50" />
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-px w-3 bg-blue-400/50" />
          </div>
        </div>
      )}
    </div>
  )
}

export function SourcePDFViewer({ lotId, productId, sourcePdfs }: SourcePDFViewerProps) {
  const [pdfDataList, setPdfDataList] = useState<PdfData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [containerWidth, setContainerWidth] = useState<number>(0)
  const containerRef = useRef<HTMLDivElement>(null)

  // Track container width with ResizeObserver
  useEffect(() => {
    if (!containerRef.current) return

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = entry.contentRect.width
        if (width > 0) {
          setContainerWidth(width)
        }
      }
    })

    observer.observe(containerRef.current)

    // Initial measurement
    const initialWidth = containerRef.current.offsetWidth
    if (initialWidth > 0) {
      setContainerWidth(initialWidth)
    }

    return () => observer.disconnect()
  }, [])

  // Fetch all PDFs
  useEffect(() => {
    if (sourcePdfs.length === 0) {
      setLoading(false)
      return
    }

    const fetchAllPdfs = async () => {
      setLoading(true)
      setError(null)

      try {
        const results: PdfData[] = []

        for (const filename of sourcePdfs) {
          const blob = await releaseApi.getSourcePdfBlob(lotId, productId, filename)
          const url = URL.createObjectURL(blob)
          results.push({ filename, url, numPages: 0 })
        }

        setPdfDataList(results)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load PDFs")
      } finally {
        setLoading(false)
      }
    }

    fetchAllPdfs()

    // Cleanup URLs on unmount
    return () => {
      pdfDataList.forEach((pdf) => {
        if (pdf.url) URL.revokeObjectURL(pdf.url)
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lotId, productId, sourcePdfs])

  const handleDocumentLoadSuccess = useCallback((index: number, numPages: number) => {
    setPdfDataList((prev) =>
      prev.map((pdf, i) => (i === index ? { ...pdf, numPages } : pdf))
    )
  }, [])

  // Calculate total pages across all PDFs
  const totalPages = pdfDataList.reduce((sum, pdf) => sum + pdf.numPages, 0)

  // Calculate global page number for a given PDF index and local page
  const getGlobalPageNumber = (pdfIndex: number, localPage: number): number => {
    let globalPage = localPage
    for (let i = 0; i < pdfIndex; i++) {
      globalPage += pdfDataList[i].numPages
    }
    return globalPage
  }

  if (sourcePdfs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="rounded-xl bg-slate-100 p-4">
          <FileText className="h-8 w-8 text-slate-400" />
        </div>
        <p className="mt-4 text-[14px] font-medium text-slate-600">No source documents</p>
        <p className="mt-1 text-[13px] text-slate-500">
          No PDF files were uploaded for this sample
        </p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        <p className="mt-3 text-[13px] text-slate-500">Loading documents...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="rounded-xl bg-red-50 p-4">
          <FileText className="h-8 w-8 text-red-400" />
        </div>
        <p className="mt-4 text-[14px] font-medium text-red-600">Failed to load documents</p>
        <p className="mt-1 text-[13px] text-slate-500">{error}</p>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="w-full h-full overflow-y-auto overflow-x-hidden">
      {pdfDataList.map((pdf, pdfIndex) => (
        <div key={pdf.filename}>
          {/* Document separator with filename */}
          {pdfIndex > 0 && (
            <div className="h-px bg-slate-300 my-4" />
          )}
          <div className="bg-slate-100 px-3 py-1.5 mb-2 rounded text-[11px] font-medium text-slate-600 truncate">
            {pdf.filename}
          </div>

          <Document
            file={pdf.url}
            onLoadSuccess={({ numPages }) => handleDocumentLoadSuccess(pdfIndex, numPages)}
            loading={
              <div className="flex items-center justify-center h-[200px]">
                <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
              </div>
            }
            error={
              <div className="flex flex-col items-center justify-center h-[200px]">
                <FileText className="h-5 w-5 text-red-400" />
                <p className="mt-2 text-[11px] text-red-500">Failed to load</p>
              </div>
            }
          >
            {pdf.numPages > 0 &&
              Array.from({ length: pdf.numPages }, (_, i) => (
                <PdfPage
                  key={`${pdf.filename}-${i}`}
                  pageNumber={i + 1}
                  width={containerWidth || 500}
                  totalPages={totalPages}
                  globalPageNumber={getGlobalPageNumber(pdfIndex, i + 1)}
                />
              ))}
          </Document>
        </div>
      ))}
    </div>
  )
}
