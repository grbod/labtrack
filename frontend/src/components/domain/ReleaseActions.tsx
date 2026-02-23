import { useState, useEffect, useCallback, useRef } from "react"
import {
  CheckCircle2,
  Download,
  Mail,
  Plus,
  Loader2,
  Clock,
  Building2,
  RefreshCw,
  ChevronDown,
} from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
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
import { useCustomers, useEmailHistory, useSendEmail, useDownloadCoa } from "@/hooks/useRelease"
import { useRetestRequests } from "@/hooks/useRetests"
import { formatDate } from "@/lib/date-utils"
import { extractApiErrorMessage } from "@/lib/api-utils"
import type { ReleaseDetails, Customer, SaveDraftData } from "@/types/release"

interface ReleaseActionsProps {
  release: ReleaseDetails
  lotId: number
  productId: number
  onSaveDraft: (data: SaveDraftData) => void
  onApprove: (customerId?: number, notes?: string) => Promise<void>
  onDone: () => void
  isSaving?: boolean
  isApproving?: boolean
}

export function ReleaseActions({
  release,
  lotId,
  productId,
  onSaveDraft,
  onApprove,
  onDone,
  isSaving,
  isApproving,
}: ReleaseActionsProps) {
  const [customerId, setCustomerId] = useState<number | null>(
    release.draft_data?.customer_id ?? release.customer_id
  )
  const [notes, setNotes] = useState(release.draft_data?.notes ?? release.notes ?? "")
  const [showCustomerAdd, setShowCustomerAdd] = useState(false)
  const [showApproveConfirm, setShowApproveConfirm] = useState(false)
  const [showSuccessDialog, setShowSuccessDialog] = useState(false)
  const [showEmailDialog, setShowEmailDialog] = useState(false)
  const [emailRecipient, setEmailRecipient] = useState("")
  const [approveError, setApproveError] = useState<string | null>(null)

  // Clear stale error when navigating between release items
  useEffect(() => {
    setApproveError(null)
  }, [lotId, productId])

  const { data: customers = [] } = useCustomers()
  const { data: emailHistory = [] } = useEmailHistory(lotId, productId)
  const { data: retestData } = useRetestRequests(lotId)
  const sendEmail = useSendEmail()
  const downloadCoa = useDownloadCoa()

  // State for retest history accordion
  const [retestExpanded, setRetestExpanded] = useState(false)
  const retestRequests = retestData?.items ?? []
  // Block release for both pending AND review_required retests
  const hasPendingRetest = retestRequests.some(
    r => r.status === "pending" || r.status === "review_required"
  )

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
    setApproveError(null)
    try {
      await onApprove(customerId ?? undefined, notes || undefined)
      setShowApproveConfirm(false)
      setShowSuccessDialog(true) // Show success dialog instead of navigating
    } catch (error: unknown) {
      console.error("Failed to approve release:", error)
      setShowApproveConfirm(false)
      const message = extractApiErrorMessage(error, "Failed to approve release", {
        403: "You don't have permission to approve releases. QC Manager or Admin role required.",
        400: "Cannot approve release. Check the error details below.",
      })
      setApproveError(message)
      toast.error(message, { duration: 5000 })
    }
  }

  const handleSuccessDone = () => {
    setShowSuccessDialog(false)
    onDone()
  }

  const handleSuccessEmailClick = () => {
    setShowSuccessDialog(false)
    setShowEmailDialog(true)
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

  const handleDownload = async () => {
    try {
      await downloadCoa.mutateAsync({ lotId, productId })
      toast.success("COA downloaded successfully")
    } catch (error) {
      console.error("Failed to download COA:", error)
      toast.error("Failed to download COA")
    }
  }

  const isReleased = release.status === "released"
  const selectedCustomer = customers.find((c) => c.id === customerId)

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

      {/* Retest History */}
      {retestRequests.length > 0 && (
        <div className="pt-2 border-t border-slate-200">
          <button
            type="button"
            onClick={() => setRetestExpanded(!retestExpanded)}
            className="w-full flex items-center justify-between text-left"
          >
            <h4 className="text-[11px] font-semibold uppercase tracking-widest text-amber-600 flex items-center gap-1.5">
              <RefreshCw className="h-3 w-3" />
              Retest History ({retestRequests.length})
            </h4>
            <ChevronDown
              className={`h-4 w-4 text-slate-400 transition-transform ${
                retestExpanded ? "rotate-180" : ""
              }`}
            />
          </button>
          {retestExpanded && (
            <div className="mt-2 space-y-2 max-h-40 overflow-y-auto">
              {retestRequests.map((request) => (
                <div
                  key={request.id}
                  className="rounded-md border border-amber-200 bg-amber-50/50 p-2 text-[12px]"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono font-medium text-amber-800">
                      {request.reference_number}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${
                        request.status === "completed"
                          ? "bg-emerald-100 text-emerald-700"
                          : request.status === "review_required"
                          ? "bg-yellow-100 text-yellow-700"
                          : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {request.status === "completed" ? "Completed" : request.status === "review_required" ? "Review" : "Pending"}
                    </span>
                  </div>
                  <p className="text-slate-600 text-[11px]">
                    Tests: {request.items.map((item) => {
                      const hasChange = item.original_value !== item.current_value &&
                                        item.original_value !== null &&
                                        item.current_value !== null
                      if (hasChange) {
                        return `${item.test_type}: ${item.original_value} → ${item.current_value}`
                      }
                      // Show original value even when no change yet (pending retest)
                      if (item.original_value) {
                        return `${item.test_type}: ${item.original_value}`
                      }
                      return item.test_type
                    }).filter(Boolean).join(", ") || "—"}
                  </p>
                  <p className="text-slate-500 text-[10px] mt-1 truncate" title={request.reason}>
                    {request.reason}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

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
        {approveError && (
          <div className="rounded-md border border-red-200 bg-red-50 p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-medium text-red-800">Release Failed</p>
                <p className="mt-1 text-xs text-red-700">{approveError}</p>
                {/signature/i.test(approveError) && (
                  <Button
                    variant="link"
                    size="sm"
                    className="mt-1 h-auto p-0 text-xs text-red-700 hover:text-red-800"
                    onClick={() => window.open("/settings", "_blank")}
                  >
                    Upload signature in Settings
                  </Button>
                )}
              </div>
              <button
                type="button"
                className="text-[11px] font-medium text-red-700 hover:text-red-800"
                onClick={() => setApproveError(null)}
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {!isReleased && (
          <TooltipProvider>
            <Tooltip open={hasPendingRetest ? undefined : false}>
              <TooltipTrigger asChild>
                <span className={hasPendingRetest ? "cursor-not-allowed w-full" : "w-full"}>
                  <Button
                    type="button"
                    className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50"
                    onClick={handleApproveClick}
                    disabled={isApproving || hasPendingRetest}
                  >
                    {isApproving ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                    Approve & Release
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                <p>Cannot release while retest is pending</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        {isReleased && (
          <div className="space-y-2">
            <p className="text-center text-[13px] text-emerald-600 font-medium py-2">
              <CheckCircle2 className="h-4 w-4 inline mr-1" />
              COA Released
            </p>
            <Button
              variant="outline"
              className="w-full"
              onClick={handleDownload}
              disabled={downloadCoa.isPending}
            >
              {downloadCoa.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Download PDF
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => setShowEmailDialog(true)}
            >
              <Mail className="h-4 w-4" />
              Email PDF
            </Button>
          </div>
        )}
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
            <Button
              type="button"
              variant="outline"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                setShowApproveConfirm(false)
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              className="bg-emerald-600 hover:bg-emerald-700"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                handleApproveConfirm()
              }}
              disabled={isApproving}
            >
              {isApproving && <Loader2 className="h-4 w-4 animate-spin" />}
              Approve & Release
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Success Dialog */}
      <Dialog
        open={showSuccessDialog}
        onOpenChange={(open) => {
          if (!open) {
            setShowSuccessDialog(false)
            onDone()
          }
        }}
      >
        <DialogContent className="sm:max-w-[400px]">
          <div className="flex flex-col items-center text-center py-4">
            <div className="rounded-full bg-emerald-100 p-3 mb-4">
              <CheckCircle2 className="h-8 w-8 text-emerald-600" />
            </div>
            <DialogTitle className="text-xl">COA Released Successfully</DialogTitle>
            <p className="text-slate-500 text-sm mt-2">
              {release.product.product_name} - Lot {release.lot.lot_number}
            </p>
          </div>
          <div className="flex flex-col gap-2 pt-2">
            <Button
              className="w-full bg-emerald-600 hover:bg-emerald-700"
              onClick={handleDownload}
              disabled={downloadCoa.isPending}
            >
              {downloadCoa.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Download PDF
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={handleSuccessEmailClick}
            >
              <Mail className="h-4 w-4" />
              Email PDF
            </Button>
          </div>
          <DialogFooter className="pt-4">
            <Button
              variant="secondary"
              className="w-full"
              onClick={handleSuccessDone}
            >
              Done
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
          <div className="py-2">
            <div className="rounded-lg bg-slate-50 p-3 mb-4">
              <div className="space-y-1.5">
                <div>
                  <p className="text-[11px] text-slate-500">Product</p>
                  <p className="text-[13px] font-medium text-slate-900">
                    {release.product.product_name}
                    {release.product.flavor && ` - ${release.product.flavor}`}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] text-slate-500">Lot Number</p>
                  <p className="text-[13px] font-mono font-medium text-slate-900">
                    {release.lot.lot_number}
                  </p>
                </div>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="emailRecipient" className="text-[12px]">
                Recipient Email
              </Label>
              <Input
                id="emailRecipient"
                type="email"
                value={emailRecipient}
                onChange={(e) => setEmailRecipient(e.target.value)}
                placeholder="Enter recipient email"
                autoFocus
              />
            </div>
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
