import { Upload, Loader2, FileText } from "lucide-react"
import { cn } from "@/lib/utils"

interface PdfUploadDropzoneProps {
  /** Whether a file is being dragged over the modal */
  isDragging: boolean
  /** Whether upload is in progress */
  isUploading: boolean
}

/**
 * Full-modal drag-and-drop overlay for PDF uploads.
 * Shows when user drags a file over the modal.
 */
export function PdfUploadDropzone({
  isDragging,
  isUploading,
}: PdfUploadDropzoneProps) {
  // Only show when dragging or uploading
  if (!isDragging && !isUploading) {
    return null
  }

  return (
    <div
      className={cn(
        "absolute inset-0 z-50 flex items-center justify-center rounded-lg pointer-events-auto",
        "bg-blue-50/95 backdrop-blur-sm",
        "border-2 border-dashed",
        isDragging ? "border-blue-400" : "border-transparent"
      )}
    >
      <div className="text-center">
        {isUploading ? (
          <>
            <div className="relative">
              <FileText className="h-12 w-12 text-blue-300 mx-auto" />
              <Loader2 className="h-6 w-6 text-blue-500 animate-spin absolute -bottom-1 -right-1" />
            </div>
            <p className="mt-4 text-lg font-semibold text-blue-700">Processing...</p>
            <p className="mt-1 text-sm text-blue-600">Uploading PDF for analysis</p>
          </>
        ) : (
          <>
            <Upload className="h-12 w-12 text-blue-500 mx-auto" />
            <p className="mt-4 text-lg font-semibold text-blue-700">Drop PDF here</p>
            <p className="mt-1 text-sm text-blue-600">Release to upload lab results</p>
          </>
        )}
      </div>
    </div>
  )
}
