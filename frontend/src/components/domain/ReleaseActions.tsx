import { useState, useEffect, useCallback, useRef } from "react"
import {
  CheckCircle2,
  Download,
  Mail,
  Plus,
  Loader2,
  Clock,
  Building2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { CustomerQuickAdd } from "./CustomerQuickAdd"
import { useCustomers, useEmailHistory, useSendEmail } from "@/hooks/useRelease"
import { releaseApi } from "@/api/release"
import type { ReleaseDetails, Customer, SaveDraftData } from "@/types/release"

interface ReleaseActionsProps {
  release: ReleaseDetails
  lotId: number
  productId: number
  onSaveDraft: (data: SaveDraftData) => void
  onApprove: (customerId?: number, notes?: string) => Promise<void>
  isSaving?: boolean
  isApproving?: boolean
}

export function ReleaseActions({
  release,
  lotId,
  productId,
  onSaveDraft,
  onApprove,
  isSaving,
  isApproving,
}: ReleaseActionsProps) {
  const [customerId, setCustomerId] = useState<number | null>(
    release.draft_data?.customer_id ?? release.customer_id
  )
  const [notes, setNotes] = useState(release.draft_data?.notes ?? release.notes ?? "")
  const [showCustomerAdd, setShowCustomerAdd] = useState(false)
  const [showApproveConfirm, setShowApproveConfirm] = useState(false)
  const [showEmailDialog, setShowEmailDialog] = useState(false)
  const [emailRecipient, setEmailRecipient] = useState("")

  const { data: customers = [] } = useCustomers()
  const { data: emailHistory = [] } = useEmailHistory(lotId, productId)
  const sendEmail = useSendEmail()

  // Debounced auto-save
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const debouncedSave = useCallback(
    (data: SaveDraftData) => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
      saveTimeoutRef.current = setTimeout(() => {
        onSaveDraft(data)
      }, 1000)
    },
    [onSaveDraft]
  )

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
    }
  }, [])

  // Auto-save on customer change
  useEffect(() => {
    if (customerId !== (release.draft_data?.customer_id ?? release.customer_id)) {
      debouncedSave({ customer_id: customerId, notes })
    }
  }, [customerId, notes, release.draft_data?.customer_id, release.customer_id, debouncedSave])

  // Auto-save on notes change
  const handleNotesChange = (value: string) => {
    setNotes(value)
    debouncedSave({ customer_id: customerId, notes: value })
  }

  const handleCustomerCreated = (customer: Customer) => {
    setCustomerId(customer.id)
  }

  const handleApproveClick = () => {
    setShowApproveConfirm(true)
  }

  const handleApproveConfirm = async () => {
    await onApprove(customerId ?? undefined, notes || undefined)
    setShowApproveConfirm(false)
  }

  const handleSendEmail = async () => {
    if (!emailRecipient.trim()) return

    try {
      await sendEmail.mutateAsync({
        lotId,
        productId,
        recipientEmail: emailRecipient.trim(),
      })
      setEmailRecipient("")
      setShowEmailDialog(false)
    } catch (error) {
      console.error("Failed to send email:", error)
    }
  }

  const isReleased = release.status === "released"
  const selectedCustomer = customers.find((c) => c.id === customerId)

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  }

  return (
    <div className="space-y-5">
      {/* Product Info Card */}
      <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
        <h3 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400 mb-3">
          Product Details
        </h3>
        <div className="space-y-2">
          <div>
            <p className="text-[12px] text-slate-500">Product</p>
            <p className="text-[13px] font-medium text-slate-900">
              {release.product.product_name}
            </p>
          </div>
          <div>
            <p className="text-[12px] text-slate-500">Brand</p>
            <p className="text-[13px] font-medium text-slate-900">
              {release.product.brand}
            </p>
          </div>
          {release.product.flavor && (
            <div>
              <p className="text-[12px] text-slate-500">Flavor</p>
              <p className="text-[13px] font-medium text-slate-900">
                {release.product.flavor}
              </p>
            </div>
          )}
          <div className="pt-2 border-t border-slate-200">
            <p className="text-[12px] text-slate-500">Lot Number</p>
            <p className="text-[13px] font-mono font-medium text-slate-900">
              {release.lot.lot_number}
            </p>
          </div>
          {release.lot.mfg_date && (
            <div>
              <p className="text-[12px] text-slate-500">Mfg Date</p>
              <p className="text-[13px] font-medium text-slate-900">
                {formatDate(release.lot.mfg_date)}
              </p>
            </div>
          )}
          {release.lot.exp_date && (
            <div>
              <p className="text-[12px] text-slate-500">Exp Date</p>
              <p className="text-[13px] font-medium text-slate-900">
                {formatDate(release.lot.exp_date)}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Customer Selection */}
      <div className="space-y-2">
        <Label className="text-[12px] text-slate-600">Customer (Optional)</Label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <select
              value={customerId ?? ""}
              onChange={(e) => setCustomerId(e.target.value ? Number(e.target.value) : null)}
              disabled={isReleased}
              className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 py-1 pr-8 text-[13px] shadow-xs appearance-none disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="">Select customer...</option>
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.company_name}
                </option>
              ))}
            </select>
          </div>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setShowCustomerAdd(true)}
            disabled={isReleased}
            title="Add new customer"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {selectedCustomer && (
          <div className="flex items-center gap-2 text-[12px] text-slate-500 mt-1">
            <Building2 className="h-3 w-3" />
            {selectedCustomer.email || "No email on file"}
          </div>
        )}
      </div>

      {/* Notes */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-[12px] text-slate-600">Notes</Label>
          {isSaving && (
            <span className="flex items-center gap-1 text-[11px] text-slate-400">
              <Loader2 className="h-3 w-3 animate-spin" />
              Saving...
            </span>
          )}
        </div>
        <textarea
          value={notes}
          onChange={(e) => handleNotesChange(e.target.value)}
          disabled={isReleased}
          placeholder="Add notes about this release..."
          className="w-full h-20 rounded-md border border-slate-200 bg-white px-3 py-2 text-[13px] shadow-xs resize-none disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      {/* Action Buttons */}
      <div className="space-y-2 pt-2">
        {!isReleased && (
          <Button
            className="w-full bg-emerald-600 hover:bg-emerald-700"
            onClick={handleApproveClick}
            disabled={isApproving}
          >
            {isApproving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            Approve & Release
          </Button>
        )}

        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1"
            disabled={!isReleased}
            asChild={isReleased}
          >
            {isReleased ? (
              <a
                href={releaseApi.getDownloadUrl(lotId, productId)}
                download
              >
                <Download className="h-4 w-4" />
                Download
              </a>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Download
              </>
            )}
          </Button>
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => setShowEmailDialog(true)}
            disabled={!isReleased}
          >
            <Mail className="h-4 w-4" />
            Email
          </Button>
        </div>
      </div>

      {/* Email History */}
      {emailHistory.length > 0 && (
        <div className="pt-2 border-t border-slate-200">
          <h4 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400 mb-2">
            Email History
          </h4>
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {emailHistory.map((entry) => (
              <div
                key={entry.id}
                className="flex items-start gap-2 text-[12px] text-slate-600"
              >
                <Clock className="h-3 w-3 mt-0.5 text-slate-400 shrink-0" />
                <div>
                  <p className="font-medium">{entry.recipient_email}</p>
                  <p className="text-slate-400">
                    {formatDate(entry.sent_at)} by {entry.sent_by}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Customer Quick Add Modal */}
      <CustomerQuickAdd
        open={showCustomerAdd}
        onOpenChange={setShowCustomerAdd}
        onCustomerCreated={handleCustomerCreated}
      />

      {/* Approve Confirmation Dialog */}
      <Dialog open={showApproveConfirm} onOpenChange={setShowApproveConfirm}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Confirm Release</DialogTitle>
            <DialogDescription>
              Are you sure you want to approve and release this COA? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApproveConfirm(false)}>
              Cancel
            </Button>
            <Button
              className="bg-emerald-600 hover:bg-emerald-700"
              onClick={handleApproveConfirm}
              disabled={isApproving}
            >
              {isApproving && <Loader2 className="h-4 w-4 animate-spin" />}
              Approve & Release
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Email Dialog */}
      <Dialog open={showEmailDialog} onOpenChange={setShowEmailDialog}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Send COA via Email</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Label htmlFor="emailRecipient">Recipient Email</Label>
            <Input
              id="emailRecipient"
              type="email"
              value={emailRecipient}
              onChange={(e) => setEmailRecipient(e.target.value)}
              placeholder="Enter recipient email"
              className="mt-2"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEmailDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSendEmail}
              disabled={!emailRecipient.trim() || sendEmail.isPending}
            >
              {sendEmail.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Send Email
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
