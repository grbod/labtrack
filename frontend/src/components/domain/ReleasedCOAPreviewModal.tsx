import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { ArrowLeft, ArrowRight, Ban, Download, ExternalLink, Loader2, Mail, X } from "lucide-react"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { COAPreview } from "@/components/domain/COAPreview"
import { useVoidRelease } from "@/hooks/useRelease"
import { useAuthStore } from "@/store/auth"
import type { ArchiveItem } from "@/types/release"

interface ReleasedCOAPreviewModalProps {
  items: ArchiveItem[]
  currentItem: ArchiveItem | null
  onCurrentItemChange: (item: ArchiveItem | null) => void
  onEmail: (item: ArchiveItem) => void
  onDownload: (lotId: number, productId: number) => void
  isDownloading: (lotId: number, productId: number) => boolean
}

function itemKey(item: Pick<ArchiveItem, "lot_id" | "product_id">) {
  return `${item.lot_id}-${item.product_id}`
}

function formatProduct(item: ArchiveItem) {
  return [
    item.product_name,
    item.flavor ? `- ${item.flavor}` : "",
    item.size ? `(${item.size})` : "",
  ]
    .filter(Boolean)
    .join(" ")
}

export function ReleasedCOAPreviewModal({
  items,
  currentItem,
  onCurrentItemChange,
  onEmail,
  onDownload,
  isDownloading,
}: ReleasedCOAPreviewModalProps) {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const isAdmin = user?.role === "admin"
  const voidRelease = useVoidRelease()
  const [showVoidDialog, setShowVoidDialog] = useState(false)
  const [voidReason, setVoidReason] = useState("")
  const currentIndex = useMemo(() => {
    if (!currentItem) return -1
    const currentKey = itemKey(currentItem)
    return items.findIndex((item) => itemKey(item) === currentKey)
  }, [currentItem, items])

  const open = !!currentItem
  const canGoPrevious = currentIndex > 0
  const canGoNext = currentIndex >= 0 && currentIndex < items.length - 1

  useEffect(() => {
    if (open && currentIndex === -1) {
      onCurrentItemChange(null)
    }
  }, [currentIndex, onCurrentItemChange, open])

  useEffect(() => {
    if (!open) return

    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const isTextInput =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT" ||
        target?.isContentEditable

      if (isTextInput) return

      if (event.key === "ArrowLeft" && canGoPrevious) {
        event.preventDefault()
        onCurrentItemChange(items[currentIndex - 1])
      } else if (event.key === "ArrowRight" && canGoNext) {
        event.preventDefault()
        onCurrentItemChange(items[currentIndex + 1])
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [canGoNext, canGoPrevious, currentIndex, items, onCurrentItemChange, open])

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      onCurrentItemChange(null)
    }
  }

  const handleVoidConfirm = async () => {
    if (!currentItem || !voidReason.trim()) return
    try {
      await voidRelease.mutateAsync({
        releaseId: currentItem.id,
        reason: voidReason.trim(),
      })
      toast.success("Release voided and returned to the queue")
      setShowVoidDialog(false)
      setVoidReason("")
      onCurrentItemChange(null)
    } catch {
      /* useVoidRelease surfaces its own error toast */
    }
  }

  if (!currentItem || currentIndex === -1) {
    return null
  }

  const downloading = isDownloading(currentItem.lot_id, currentItem.product_id)

  return (
    <>
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="flex h-[90vh] w-[95vw] max-w-4xl flex-col gap-0 overflow-hidden p-0 sm:max-w-4xl"
      >
        <DialogHeader className="shrink-0 gap-0 border-b border-slate-200 px-5 py-3 text-left">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-baseline gap-2.5">
                <DialogTitle className="truncate font-mono text-[16px] font-semibold text-slate-900">
                  {currentItem.reference_number}
                </DialogTitle>
                <span className="shrink-0 text-[12px] tabular-nums text-slate-400">
                  {currentIndex + 1} / {items.length}
                </span>
              </div>
              <DialogDescription className="sr-only">
                Read-only Certificate of Analysis preview for the selected released row.
              </DialogDescription>
              <p className="mt-0.5 truncate text-[12px] text-slate-500">
                Lot {currentItem.lot_number || "—"} · {formatProduct(currentItem)}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  title="Previous (←)"
                  aria-label="Previous"
                  onClick={() => onCurrentItemChange(items[currentIndex - 1])}
                  disabled={!canGoPrevious}
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  title="Next (→)"
                  aria-label="Next"
                  onClick={() => onCurrentItemChange(items[currentIndex + 1])}
                  disabled={!canGoNext}
                >
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
              <div className="mx-0.5 h-5 w-px bg-slate-200" />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onDownload(currentItem.lot_id, currentItem.product_id)}
                disabled={downloading}
              >
                {downloading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                Download
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  onCurrentItemChange(null)
                  onEmail(currentItem)
                }}
              >
                <Mail className="h-4 w-4" />
                Re-send Email
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => navigate(`/audittrail/lot/${currentItem.lot_id}/${currentItem.product_id}`)}
              >
                <ExternalLink className="h-4 w-4" />
                Open Full Detail
              </Button>
              {isAdmin && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="border-red-200 text-red-700 hover:bg-red-50"
                  onClick={() => setShowVoidDialog(true)}
                >
                  <Ban className="h-4 w-4" />
                  Void &amp; Return to Queue
                </Button>
              )}
              <div className="mx-0.5 h-5 w-px bg-slate-200" />
              <DialogClose asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Close preview"
                >
                  <X className="h-4 w-4" />
                </Button>
              </DialogClose>
            </div>
          </div>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-hidden bg-slate-100">
          <COAPreview
            lotId={currentItem.lot_id}
            productId={currentItem.product_id}
            readOnly
            showRetestOriginals={false}
          />
        </div>
      </DialogContent>
    </Dialog>

    <Dialog
      open={showVoidDialog}
      onOpenChange={(nextOpen) => {
        setShowVoidDialog(nextOpen)
        if (!nextOpen) setVoidReason("")
      }}
    >
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>Void Release</DialogTitle>
          <DialogDescription>
            This returns the lot to the release queue. The COA must be re-approved
            before it can be released again.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="voidReason" className="text-[12px]">
            Reason (required)
          </Label>
          <Textarea
            id="voidReason"
            value={voidReason}
            onChange={(e) => setVoidReason(e.target.value)}
            placeholder="Why is this release being voided?"
            rows={3}
            autoFocus
          />
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setShowVoidDialog(false)
              setVoidReason("")
            }}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleVoidConfirm}
            disabled={!voidReason.trim() || voidRelease.isPending}
            className="bg-red-600 text-white hover:bg-red-700"
          >
            {voidRelease.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Void &amp; Return to Queue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  )
}
