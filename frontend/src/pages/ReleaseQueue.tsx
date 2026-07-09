import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { Loader2, Inbox, CheckCircle2, Download, Mail, Search, ArrowRight } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ReleasedCOAPreviewModal } from "@/components/domain/ReleasedCOAPreviewModal"
import { useReleaseQueue, useRecentlyReleased, useDownloadWithTracking, useSendEmail } from "@/hooks/useRelease"
import { useReturnLotForReview, useRejectLot } from "@/hooks/useLots"
import { useAuthStore } from "@/store/auth"
import { formatDate } from "@/lib/date-utils"
import { toast } from "sonner"
import type { ReleaseQueueItem, ArchiveItem } from "@/types/release"

export function ReleaseQueuePage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const canAct = user?.role === "admin" || user?.role === "qc_manager"
  const [recentDays, setRecentDays] = useState(7)
  const [search, setSearch] = useState("")
  const [showEmailDialog, setShowEmailDialog] = useState(false)
  const [emailRecipient, setEmailRecipient] = useState("")
  const [selectedItem, setSelectedItem] = useState<ArchiveItem | null>(null)
  const [previewItem, setPreviewItem] = useState<ArchiveItem | null>(null)
  const [actionDialog, setActionDialog] = useState<{ mode: "return" | "reject"; item: ReleaseQueueItem } | null>(null)
  const [actionReason, setActionReason] = useState("")
  const { data: queue = [], isLoading } = useReleaseQueue()
  const { data: recentData, isLoading: isLoadingRecent } = useRecentlyReleased(recentDays)
  const recentlyReleased = recentData?.items ?? []
  const recentTotal = recentData?.total ?? 0
  // The archive query is capped at 100 items; a larger window total means the
  // list below is truncated and older releases live only in History.
  const isRecentTruncated = recentTotal > recentlyReleased.length
  const { handleDownload: downloadCoa, isDownloading } = useDownloadWithTracking()
  const sendEmail = useSendEmail()
  const returnMutation = useReturnLotForReview()
  const rejectMutation = useRejectLot()

  // Filter recently released based on search
  const filteredReleased = recentlyReleased.filter((item) => {
    if (!search.trim()) return true
    const searchLower = search.toLowerCase()
    return (
      item.product_name?.toLowerCase().includes(searchLower) ||
      item.lot_number?.toLowerCase().includes(searchLower) ||
      item.reference_number?.toLowerCase().includes(searchLower) ||
      item.brand?.toLowerCase().includes(searchLower) ||
      item.customer_name?.toLowerCase().includes(searchLower)
    )
  })

  const handleAwaitingReleaseRowClick = (item: ReleaseQueueItem) => {
    navigate(`/release/${item.lot_id}/${item.product_id}`)
  }

  const handleDownload = (e: React.MouseEvent, lotId: number, productId: number) => {
    e.stopPropagation() // Prevent row click navigation
    downloadCoa(lotId, productId)
  }

  const openEmailDialog = (item: ArchiveItem) => {
    setSelectedItem(item)
    setEmailRecipient(item.customer_email ?? "")
    setShowEmailDialog(true)
  }

  const handleEmailClick = (e: React.MouseEvent, item: ArchiveItem) => {
    e.stopPropagation() // Prevent row click navigation
    openEmailDialog(item)
  }

  const handleSendEmail = async () => {
    if (!emailRecipient.trim() || !selectedItem) return

    try {
      await sendEmail.mutateAsync({
        lotId: selectedItem.lot_id,
        productId: selectedItem.product_id,
        recipientEmail: emailRecipient.trim(),
      })
      setEmailRecipient("")
      setShowEmailDialog(false)
      setSelectedItem(null)
    } catch (error) {
      console.error("Failed to send email:", error)
    }
  }

  const handleActionClick = (e: React.MouseEvent, mode: "return" | "reject", item: ReleaseQueueItem) => {
    e.stopPropagation()
    setActionReason("")
    setActionDialog({ mode, item })
  }

  const handleActionConfirm = async () => {
    if (!actionDialog || !actionReason.trim()) return
    const { mode, item } = actionDialog
    try {
      if (mode === "return") {
        await returnMutation.mutateAsync({ lotId: item.lot_id, reason: actionReason.trim() })
        toast.success("Lot returned to Sample Tracker")
      } else {
        await rejectMutation.mutateAsync({ lotId: item.lot_id, reason: actionReason.trim() })
        toast.success("Lot rejected")
      }
      setActionDialog(null)
      setActionReason("")
    } catch {
      // error toast handled in mutation onError
    }
  }

  const handleActionDialogClose = (open: boolean) => {
    if (!open) {
      setActionDialog(null)
      setActionReason("")
    }
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.275 }}
        className="space-y-8"
      >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">
            Release Queue
          </h1>
          <p className="mt-1.5 text-[15px] text-slate-500">
            COAs awaiting final approval and release
          </p>
        </div>
      </div>

      {/* Awaiting Release Table */}
      <div className="space-y-4">
        <h2 className="text-[18px] font-semibold text-slate-900">
          Awaiting Release
        </h2>
        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
          </div>
        ) : queue.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="rounded-xl bg-slate-100 p-4">
              <Inbox className="h-8 w-8 text-slate-400" />
            </div>
            <p className="mt-4 text-[14px] font-medium text-slate-600">
              No COAs awaiting release
            </p>
            <p className="mt-1 text-[13px] text-slate-500">
              Submitted samples will appear here for final release
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/80">
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Ref
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Lot
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Brand
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Product
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Created Date
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Status
                </TableHead>
                {canAct && (
                  <TableHead className="text-[12px] font-semibold text-slate-600 w-[220px]">
                    Actions
                  </TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.map((item) => (
                <TableRow
                  key={`${item.lot_id}-${item.product_id}`}
                  className="cursor-pointer hover:bg-slate-50/80 transition-colors"
                  onClick={() => handleAwaitingReleaseRowClick(item)}
                >
                  <TableCell className="font-mono text-[13px] font-medium text-slate-900">
                    {item.reference_number}
                  </TableCell>
                  <TableCell className="font-mono text-[13px] text-slate-700">
                    {item.lot_number}
                  </TableCell>
                  <TableCell className="text-[13px] text-slate-600">
                    {item.brand}
                  </TableCell>
                  <TableCell className="text-[13px] text-slate-700">
                    {item.product_name}
                    {item.flavor && (
                      <span className="text-slate-500"> - {item.flavor}</span>
                    )}
                    {item.size && (
                      <span className="text-slate-400 ml-1">({item.size})</span>
                    )}
                  </TableCell>
                  <TableCell className="text-[13px] text-slate-600">
                    {formatDate(item.created_at)}
                  </TableCell>
                  <TableCell>
                    {item.release_status === "forked" ? (
                      <Badge variant="outline" className="text-[11px] border-sky-300 text-sky-700">
                        Forked{item.forked_to_reference ? ` → ${item.forked_to_reference}` : ""}
                      </Badge>
                    ) : (
                      <Badge variant="amber" className="text-[11px]">
                        Awaiting Release
                      </Badge>
                    )}
                  </TableCell>
                  {canAct && (
                    <TableCell>
                      {item.release_status === "forked" ? (
                        <span className="text-[12px] text-slate-400">
                          Individualized — no action
                        </span>
                      ) : (
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => handleActionClick(e, "return", item)}
                            className="h-8 text-[12px] text-amber-700 hover:bg-amber-50 border-amber-200"
                          >
                            Return for Review
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => handleActionClick(e, "reject", item)}
                            className="h-8 text-[12px] text-red-600 hover:bg-red-50 border-red-200"
                          >
                            Reject
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        </div>
      </div>

      {/* Recently Released Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <h2 className="text-[18px] font-semibold text-slate-900">
            Recently Released
          </h2>
          <div className="flex-1" />
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
          <Select
            value={recentDays.toString()}
            onValueChange={(value) => setRecentDays(Number(value))}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Past 7 days</SelectItem>
              <SelectItem value="30">Past 30 days</SelectItem>
              <SelectItem value="60">Past 60 days</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
          {isLoadingRecent ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
            </div>
          ) : filteredReleased.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16">
              <div className="rounded-xl bg-slate-100 p-4">
                <CheckCircle2 className="h-8 w-8 text-slate-400" />
              </div>
              <p className="mt-4 text-[14px] font-medium text-slate-600">
                {search.trim() ? "No matching releases found" : `No releases in the past ${recentDays} days`}
              </p>
              <p className="mt-1 text-[13px] text-slate-500">
                {search.trim() ? "Try adjusting your search" : "Released COAs will appear here"}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80">
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Ref
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Lot
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Brand
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Product
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Released Date
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Customer
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Status
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600 w-[180px]">
                    Actions
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredReleased.map((item) => (
                  <TableRow
                    key={`${item.lot_id}-${item.product_id}`}
                    className="cursor-pointer hover:bg-slate-50/80 transition-colors"
                    onClick={() => setPreviewItem(item)}
                  >
                    <TableCell className="font-mono text-[13px] font-medium text-slate-900">
                      {item.reference_number}
                    </TableCell>
                    <TableCell className="font-mono text-[13px] text-slate-700">
                      {item.lot_number}
                    </TableCell>
                    <TableCell className="text-[13px] text-slate-600">
                      {item.brand}
                    </TableCell>
                    <TableCell className="text-[13px] text-slate-700">
                      {item.product_name}
                      {item.flavor && (
                        <span className="text-slate-500"> - {item.flavor}</span>
                      )}
                      {item.size && (
                        <span className="text-slate-400 ml-1">({item.size})</span>
                      )}
                    </TableCell>
                    <TableCell className="text-[13px] text-slate-600">
                      {formatDate(item.released_at)}
                    </TableCell>
                    <TableCell className="text-[13px] text-slate-600">
                      {item.customer_name || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="emerald" className="text-[11px]">
                        Released
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => handleDownload(e, item.lot_id, item.product_id)}
                          disabled={isDownloading(item.lot_id, item.product_id)}
                          className={`h-8 text-[12px] ${isDownloading(item.lot_id, item.product_id) ? "cursor-wait" : ""}`}
                        >
                          {isDownloading(item.lot_id, item.product_id) ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Download className="h-3 w-3" />
                          )}
                          Download
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => handleEmailClick(e, item)}
                          className="h-8 text-[12px]"
                        >
                          <Mail className="h-3 w-3" />
                          Email
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>

        {/* Footer: window total + link into full History */}
        {!isLoadingRecent && recentTotal > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-2 px-1">
            <p className="text-[12px] text-slate-500">
              {isRecentTruncated ? (
                <>
                  Showing {recentlyReleased.length} of {recentTotal} releases in the past{" "}
                  {recentDays} days. Older or additional releases are in History.
                </>
              ) : (
                <>
                  {recentTotal} release{recentTotal === 1 ? "" : "s"} in the past {recentDays} days.
                </>
              )}
            </p>
            <button
              type="button"
              onClick={() => {
                const dateFrom = new Date()
                dateFrom.setDate(dateFrom.getDate() - recentDays)
                const dateFromStr = dateFrom.toISOString().split("T")[0]
                navigate(`/archive?date_from=${dateFromStr}`)
              }}
              className="inline-flex items-center gap-1 text-[13px] font-medium text-slate-600 hover:text-slate-900 transition-colors"
            >
              View all in History
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
      </motion.div>

      {/* Action Dialog (Return for Review / Reject) */}
      <Dialog open={!!actionDialog} onOpenChange={handleActionDialogClose}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>
              {actionDialog?.mode === "return" ? "Return for Review" : "Reject Lot"}
            </DialogTitle>
          </DialogHeader>
          {actionDialog && (
            <div className="py-2">
              <div className="rounded-lg bg-slate-50 p-3 mb-4">
                <div className="space-y-1.5">
                  <div>
                    <p className="text-[11px] text-slate-500">Product</p>
                    <p className="text-[13px] font-medium text-slate-900">
                      {actionDialog.item.product_name}
                      {actionDialog.item.flavor && ` - ${actionDialog.item.flavor}`}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] text-slate-500">Lot Number</p>
                    <p className="text-[13px] font-mono font-medium text-slate-900">
                      {actionDialog.item.lot_number}
                    </p>
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="actionReason" className="text-[12px]">
                  {actionDialog.mode === "return"
                    ? "Reason - what needs to be corrected?"
                    : "Rejection reason"}
                </Label>
                <Textarea
                  id="actionReason"
                  value={actionReason}
                  onChange={(e) => setActionReason(e.target.value)}
                  placeholder={
                    actionDialog.mode === "return"
                      ? "Describe what needs to be corrected..."
                      : "Provide a reason for rejection..."
                  }
                  rows={3}
                  autoFocus
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleActionDialogClose(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleActionConfirm}
              disabled={
                !actionReason.trim() ||
                returnMutation.isPending ||
                rejectMutation.isPending
              }
              className={
                actionDialog?.mode === "reject"
                  ? "bg-red-600 hover:bg-red-700 text-white"
                  : "bg-amber-600 hover:bg-amber-700 text-white"
              }
            >
              {(returnMutation.isPending || rejectMutation.isPending) && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
              {actionDialog?.mode === "return" ? "Return for Review" : "Reject Lot"}
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
          {selectedItem && (
            <div className="py-2">
              <div className="rounded-lg bg-slate-50 p-3 mb-4">
                <div className="space-y-1.5">
                  <div>
                    <p className="text-[11px] text-slate-500">Product</p>
                    <p className="text-[13px] font-medium text-slate-900">
                      {selectedItem.product_name}
                      {selectedItem.flavor && ` - ${selectedItem.flavor}`}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] text-slate-500">Lot Number</p>
                    <p className="text-[13px] font-mono font-medium text-slate-900">
                      {selectedItem.lot_number}
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
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowEmailDialog(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleSendEmail}
              disabled={!emailRecipient.trim() || sendEmail.isPending}
            >
              {sendEmail.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Send Email
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ReleasedCOAPreviewModal
        items={filteredReleased}
        currentItem={previewItem}
        onCurrentItemChange={setPreviewItem}
        onEmail={openEmailDialog}
        onDownload={downloadCoa}
        isDownloading={isDownloading}
      />
    </div>
  )
}
