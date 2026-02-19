import { useState, useEffect } from "react"
import { ChevronDown, RefreshCw, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { formatDate } from "@/lib/date-utils"
import { useRetestRequests, useDownloadRetestPdf } from "@/hooks/useRetests"
import { RetestStatusBadge } from "../RetestStatusBadge"

interface RetestsHistoryAccordionProps {
  /** Lot ID to fetch retest requests for */
  lotId: number
  /** Whether to auto-expand when pending retests exist */
  autoExpandWhenPending?: boolean
}

/**
 * Collapsible accordion showing retest request history for a lot.
 * Displays table with: Reference, Date, Status, Tests, Reason
 */
export function RetestsHistoryAccordion({
  lotId,
  autoExpandWhenPending = true
}: RetestsHistoryAccordionProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // Fetch retest requests for this lot
  const { data: retestData, isLoading } = useRetestRequests(lotId)
  const downloadPdfMutation = useDownloadRetestPdf()

  const retestRequests = retestData?.items ?? []
  const hasPendingRetests = retestRequests.some(r => r.status === "pending" || r.status === "review_required")

  // Auto-expand when pending retests and autoExpandWhenPending is true
  useEffect(() => {
    if (autoExpandWhenPending && hasPendingRetests && !isLoading) {
      setIsExpanded(true)
    }
  }, [autoExpandWhenPending, hasPendingRetests, isLoading])

  // Don't render if no retest requests
  if (!isLoading && retestRequests.length === 0) {
    return null
  }

  const handleDownloadPdf = async (requestId: number) => {
    try {
      await downloadPdfMutation.mutateAsync(requestId)
    } catch (error) {
      console.error("Failed to download PDF:", error)
    }
  }

  return (
    <Collapsible open={isExpanded} onOpenChange={setIsExpanded} className="mt-4">
      <CollapsibleTrigger
        className={cn(
          "flex items-center justify-between w-full px-4 py-3 rounded-lg transition-colors",
          "bg-amber-50 hover:bg-amber-100",
          isExpanded && "rounded-b-none"
        )}
      >
        <span className="text-sm font-medium text-amber-800 flex items-center gap-2">
          <RefreshCw className="h-4 w-4" />
          Retest History ({retestRequests.length})
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-amber-600 transition-transform",
            isExpanded && "rotate-180"
          )}
        />
      </CollapsibleTrigger>

      <CollapsibleContent
        className={cn(
          "border border-t-0 border-amber-200 rounded-b-lg bg-white",
          "data-[state=open]:animate-collapsible-down",
          "data-[state=closed]:animate-collapsible-up"
        )}
      >
        <div className="p-4">
          {isLoading ? (
            <div className="py-4 text-center text-sm text-slate-500">
              Loading retest history...
            </div>
          ) : (
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="w-32">Reference</TableHead>
                    <TableHead className="w-28">Date</TableHead>
                    <TableHead className="w-24">Status</TableHead>
                    <TableHead>Tests</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead className="w-20"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {retestRequests.map((request) => (
                    <TableRow key={request.id}>
                      <TableCell className="font-mono font-medium text-slate-900">
                        {request.reference_number}
                      </TableCell>
                      <TableCell className="text-slate-600 text-sm">
                        {formatDate(request.created_at)}
                      </TableCell>
                      <TableCell><RetestStatusBadge status={request.status} /></TableCell>
                      <TableCell className="text-sm text-slate-600">
                        {request.items.map((item) => item.test_type).filter(Boolean).join(", ") || "—"}
                      </TableCell>
                      <TableCell className="text-sm text-slate-600 max-w-xs truncate" title={request.reason}>
                        {request.reason}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDownloadPdf(request.id)}
                          disabled={downloadPdfMutation.isPending}
                          className="h-8 w-8 p-0"
                          title="Download PDF"
                        >
                          <Download className="h-4 w-4 text-slate-500" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
