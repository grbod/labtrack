import { useState } from "react"
import {
  Loader2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Filter,
  CheckCheck,
  Clock,
  AlertTriangle,
  ClipboardCheck,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

import {
  useTestResults,
  usePendingReviewCount,
  useApproveTestResult,
  useBulkApproveTestResults,
} from "@/hooks/useTestResults"
import type { TestResult } from "@/types"

export function ApprovalsPage() {
  const [page, setPage] = useState(1)
  const [showDraftOnly, setShowDraftOnly] = useState(true)
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  const { data, isLoading } = useTestResults({
    page,
    page_size: 50,
    status: showDraftOnly ? "draft" : undefined,
  })
  const { data: pendingCount } = usePendingReviewCount()
  const approveMutation = useApproveTestResult()
  const bulkApproveMutation = useBulkApproveTestResults()

  const handleApprove = async (id: number) => {
    await approveMutation.mutateAsync({ id, status: "approved" })
  }

  const handleReject = async (id: number) => {
    await approveMutation.mutateAsync({ id, status: "draft", notes: "Rejected for review" })
  }

  const handleBulkApprove = async () => {
    if (selectedIds.length === 0) return
    await bulkApproveMutation.mutateAsync({
      resultIds: selectedIds,
      status: "approved",
    })
    setSelectedIds([])
  }

  const toggleSelection = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    )
  }

  const toggleSelectAll = () => {
    if (!data) return
    const draftIds = data.items.filter((r) => r.status === "draft").map((r) => r.id)
    if (selectedIds.length === draftIds.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(draftIds)
    }
  }

  const getStatusBadge = (result: TestResult) => {
    if (result.status === "approved") {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide bg-emerald-100 text-emerald-700">
          <CheckCircle2 className="h-3 w-3" />
          Approved
        </span>
      )
    }
    if (result.confidence_score !== null && result.confidence_score < 0.7) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide bg-amber-100 text-amber-700">
          <AlertCircle className="h-3 w-3" />
          Needs Review
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide bg-slate-100 text-slate-600">
        Draft
      </span>
    )
  }

  const draftItems = data?.items.filter((r) => r.status === "draft") || []
  const lowConfidenceCount = data?.items.filter((r) => r.confidence_score !== null && r.confidence_score < 0.7).length ?? 0

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Approvals</h1>
          <p className="mt-1.5 text-[15px] text-slate-500">
            Review and approve test results
          </p>
        </div>
        {selectedIds.length > 0 && (
          <Button
            onClick={handleBulkApprove}
            disabled={bulkApproveMutation.isPending}
            className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm h-10 px-4"
          >
            {bulkApproveMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCheck className="mr-2 h-4 w-4" />
            )}
            Approve Selected ({selectedIds.length})
          </Button>
        )}
      </div>

      {/* Stats */}
      <div className="grid gap-5 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-amber-50 p-3 shadow-sm">
              <Clock className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-[28px] font-bold text-slate-900 leading-none">
                {pendingCount?.pending_count ?? 0}
              </p>
              <p className="mt-1 text-[13px] text-slate-500">Pending Review</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-emerald-50 p-3 shadow-sm">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-[28px] font-bold text-slate-900 leading-none">
                {data?.items.filter((r) => r.status === "approved").length ?? 0}
              </p>
              <p className="mt-1 text-[13px] text-slate-500">Approved</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-red-50 p-3 shadow-sm">
              <AlertTriangle className="h-5 w-5 text-red-600" />
            </div>
            <div>
              <p className="text-[28px] font-bold text-slate-900 leading-none">{lowConfidenceCount}</p>
              <p className="mt-1 text-[13px] text-slate-500">Low Confidence</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-4">
        <Button
          variant={showDraftOnly ? "default" : "outline"}
          size="sm"
          onClick={() => {
            setShowDraftOnly(!showDraftOnly)
            setPage(1)
          }}
          className={showDraftOnly ? "bg-slate-900 hover:bg-slate-800 shadow-sm h-9" : "border-slate-200 h-9"}
        >
          <Filter className="mr-2 h-4 w-4" />
          {showDraftOnly ? "Showing Draft Only" : "Show All"}
        </Button>
        <span className="text-[14px] font-medium text-slate-500">
          {data?.total ?? 0} results
        </span>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
          </div>
        ) : data?.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="w-16 h-16 rounded-2xl bg-emerald-100 flex items-center justify-center">
              <ClipboardCheck className="h-8 w-8 text-emerald-500" />
            </div>
            <p className="mt-5 text-[15px] font-medium text-slate-600">No test results to review</p>
            <p className="mt-1 text-[14px] text-slate-500">All caught up! Check back later for new results.</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100">
                <TableHead className="w-[40px]">
                  <input
                    type="checkbox"
                    checked={
                      draftItems.length > 0 &&
                      selectedIds.length === draftItems.length
                    }
                    onChange={toggleSelectAll}
                    className="rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                  />
                </TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Lot</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Test Type</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Result</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Specification</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Status</TableHead>
                <TableHead className="w-[120px] font-semibold text-slate-600 text-[13px] tracking-wide">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((result) => (
                <TableRow key={result.id} className="hover:bg-slate-50/50 transition-colors">
                  <TableCell>
                    {result.status === "draft" && (
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(result.id)}
                        onChange={() => toggleSelection(result.id)}
                        className="rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                      />
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-[13px] font-semibold text-slate-900 tracking-wide">
                    {result.lot_reference || result.lot_number || `Lot #${result.lot_id}`}
                  </TableCell>
                  <TableCell className="font-medium text-slate-700 text-[14px]">{result.test_type}</TableCell>
                  <TableCell className="text-slate-700 text-[14px]">
                    {result.result_value || "-"}
                    {result.unit && (
                      <span className="text-slate-500 ml-1">{result.unit}</span>
                    )}
                  </TableCell>
                  <TableCell className="text-slate-500 text-[13px]">
                    {result.specification || "-"}
                  </TableCell>
                  <TableCell>{getStatusBadge(result)}</TableCell>
                  <TableCell>
                    {result.status === "draft" ? (
                      <div className="flex items-center gap-0.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleApprove(result.id)}
                          disabled={approveMutation.isPending}
                          title="Approve"
                          className="h-8 w-8 p-0 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 rounded-lg transition-colors"
                        >
                          <CheckCircle2 className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleReject(result.id)}
                          disabled={approveMutation.isPending}
                          title="Reject"
                          className="h-8 w-8 p-0 text-red-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        >
                          <XCircle className="h-4 w-4" />
                        </Button>
                      </div>
                    ) : (
                      <span className="text-[12px] text-slate-500">
                        {result.approved_at
                          ? new Date(result.approved_at).toLocaleDateString()
                          : "-"}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-5 py-4">
            <p className="text-[14px] text-slate-500">
              Page {data.page} of {data.total_pages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="border-slate-200 hover:bg-slate-50 h-9"
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page === data.total_pages}
                className="border-slate-200 hover:bg-slate-50 h-9"
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
