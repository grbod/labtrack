import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

/**
 * Confirmation dialog with an optional free-text reason. Controlled via `open` +
 * `onOpenChange`; `onConfirm` receives the trimmed reason (empty string when
 * left blank). The reason field resets each time the dialog opens.
 */
export function ReasonDialog({
  open,
  onOpenChange,
  title,
  description,
  reasonLabel = "Reason (optional)",
  placeholder,
  confirmLabel,
  destructive = true,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  reasonLabel?: string
  placeholder?: string
  confirmLabel: string
  destructive?: boolean
  onConfirm: (reason: string) => void
}) {
  const [reason, setReason] = useState("")

  // Reset on every close path (Cancel, Esc, overlay, X, or confirm) so a
  // reopened dialog never shows stale text.
  const handleOpenChange = (next: boolean) => {
    if (!next) setReason("")
    onOpenChange(next)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="reason-dialog-textarea" className="text-[13px] font-medium text-slate-700">
            {reasonLabel}
          </Label>
          <Textarea
            id="reason-dialog-textarea"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={placeholder}
            className="min-h-[72px]"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Keep as is
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            onClick={() => {
              onConfirm(reason.trim())
              handleOpenChange(false)
            }}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
