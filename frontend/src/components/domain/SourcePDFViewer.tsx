import { FileText } from "lucide-react"
import { releaseApi } from "@/api/release"

interface SourcePDFViewerProps {
  lotId: number
  productId: number
  sourcePdfs: string[]
}

export function SourcePDFViewer({ lotId, productId, sourcePdfs }: SourcePDFViewerProps) {
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

  return (
    <div className="space-y-4">
      {sourcePdfs.map((filename, index) => {
        const pdfUrl = releaseApi.getSourcePdfUrl(lotId, productId, filename)
        return (
          <div key={filename} className="rounded-lg border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 px-3 py-2 border-b border-slate-200">
              <p className="text-[12px] font-medium text-slate-600 truncate" title={filename}>
                {index + 1}. {filename}
              </p>
            </div>
            <object
              data={pdfUrl}
              type="application/pdf"
              className="w-full h-[400px]"
            >
              <div className="flex flex-col items-center justify-center h-[400px] bg-slate-50">
                <FileText className="h-8 w-8 text-slate-400" />
                <p className="mt-2 text-[13px] text-slate-500">Unable to display PDF</p>
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 text-[13px] font-medium text-blue-600 hover:text-blue-700"
                >
                  Open in new tab
                </a>
              </div>
            </object>
          </div>
        )
      })}
    </div>
  )
}
