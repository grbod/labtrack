import { useState } from "react"
import { format } from "date-fns"
import { Download, History, Clock, Building2, AlertCircle, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { AuditTrailModal } from "./AuditTrailModal"
import { useEmailHistory, useDownloadCoa } from "@/hooks/useRelease"
import type { ReleaseDetails } from "@/types/release"

interface ArchiveLotActionsProps {
  release: ReleaseDetails
  lotId: number
  productId: number
  rejectionReason?: string | null
}

export function ArchiveLotActions({
  release,
  lotId,
  productId,
  rejectionReason,
}: ArchiveLotActionsProps) {
  const [showAuditModal, setShowAuditModal] = useState(false)

  const { data: emailHistory = [] } = useEmailHistory(lotId, productId)
  const downloadCoa = useDownloadCoa()

  const isReleased = release.status === "released"

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return "—"
    return format(new Date(dateStr), "MMM d, yyyy")
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

  return (
    <div className="space-y-5">
      {/* Status Badge */}
      <div className="flex items-center justify-center">
        <Badge
          variant={isReleased ? "emerald" : "destructive"}
          className="text-[12px] px-3 py-1"
        >
          {isReleased ? "Released" : "Rejected"}
        </Badge>
      </div>

      {/* Rejection Reason (if rejected) */}
      {!isReleased && rejectionReason && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-red-600 mb-1">
                Rejection Reason
              </p>
              <p className="text-[13px] text-red-700">{rejectionReason}</p>
            </div>
          </div>
        </div>
      )}

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

      {/* Customer (read-only) */}
      {release.customer && (
        <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
          <h3 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400 mb-2">
            Customer
          </h3>
          <p className="text-[13px] font-medium text-slate-900">
            {release.customer.company_name}
          </p>
          <div className="flex items-center gap-2 text-[12px] text-slate-500 mt-1">
            <Building2 className="h-3 w-3" />
            {release.customer.email || "No email on file"}
          </div>
        </div>
      )}

      {/* Notes (read-only) */}
      {release.notes && (
        <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
          <h3 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400 mb-2">
            Notes
          </h3>
          <p className="text-[13px] text-slate-700 whitespace-pre-wrap">
            {release.notes}
          </p>
        </div>
      )}

      {/* Release Date */}
      {release.released_at && (
        <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
          <h3 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400 mb-2">
            Released
          </h3>
          <p className="text-[13px] font-medium text-slate-900">
            {format(new Date(release.released_at), "MMM d, yyyy 'at' h:mm a")}
          </p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="space-y-2 pt-2">
        {/* View Audit Trail - Primary action */}
        <Button
          className="w-full"
          variant="default"
          onClick={() => setShowAuditModal(true)}
        >
          <History className="h-4 w-4" />
          View Audit Trail
        </Button>

        {/* Download COA (only for released) */}
        {isReleased && (
          <Button
            variant="outline"
            className="w-full"
            disabled={downloadCoa.isPending}
            onClick={handleDownload}
          >
            {downloadCoa.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Download COA
          </Button>
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

      {/* Audit Trail Modal */}
      <AuditTrailModal
        open={showAuditModal}
        onOpenChange={setShowAuditModal}
        lotId={lotId}
        referenceNumber={release.lot.reference_number}
      />
    </div>
  )
}
