import { useState } from "react"
import {
  Loader2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Filter,
  CheckCheck,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"

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

  const { data, isLoading, refetch } = useTestResults({
    page,
    page_size: 50,
    status: showDraftOnly ? "DRAFT" : undefined,
  })
  const { data: pendingCount } = usePendingReviewCount()
  const approveMutation = useApproveTestResult()
  const bulkApproveMutation = useBulkApproveTestResults()

  const handleApprove = async (id: number) => {
    await approveMutation.mutateAsync({ id, status: "APPROVED" })
  }

  const handleReject = async (id: number) => {
    await approveMutation.mutateAsync({ id, status: "DRAFT", notes: "Rejected for review" })
  }

  const handleBulkApprove = async () => {
    if (selectedIds.length === 0) return
    await bulkApproveMutation.mutateAsync({
      resultIds: selectedIds,
      status: "APPROVED",
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
    const draftIds = data.items.filter((r) => r.status === "DRAFT").map((r) => r.id)
    if (selectedIds.length === draftIds.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(draftIds)
    }
  }

  const getStatusBadge = (result: TestResult) => {
    if (result.status === "APPROVED") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
          <CheckCircle2 className="h-3 w-3" />
          Approved
        </span>
      )
    }
    if (result.confidence_score !== null && result.confidence_score < 0.7) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
          <AlertCircle className="h-3 w-3" />
          Needs Review
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
        Draft
      </span>
    )
  }

  const draftItems = data?.items.filter((r) => r.status === "DRAFT") || []

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Approvals</h1>
          <p className="text-muted-foreground text-sm">
            Review and approve test results
          </p>
        </div>
        {selectedIds.length > 0 && (
          <Button
            onClick={handleBulkApprove}
            disabled={bulkApproveMutation.isPending}
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
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{pendingCount?.pending_count ?? 0}</div>
            <p className="text-xs text-muted-foreground">Pending Review</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">
              {data?.items.filter((r) => r.status === "APPROVED").length ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">Approved Today</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">
              {data?.items.filter((r) => r.confidence_score !== null && r.confidence_score < 0.7).length ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">Low Confidence</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex gap-4 items-center">
            <Button
              variant={showDraftOnly ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setShowDraftOnly(!showDraftOnly)
                setPage(1)
              }}
            >
              <Filter className="mr-2 h-4 w-4" />
              {showDraftOnly ? "Showing Draft Only" : "Show All"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            {data?.total ?? 0} Test Results
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40px]">
                    <input
                      type="checkbox"
                      checked={
                        draftItems.length > 0 &&
                        selectedIds.length === draftItems.length
                      }
                      onChange={toggleSelectAll}
                      className="rounded border-gray-300"
                    />
                  </TableHead>
                  <TableHead>Lot</TableHead>
                  <TableHead>Test Type</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead>Specification</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[120px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((result) => (
                  <TableRow key={result.id}>
                    <TableCell>
                      {result.status === "DRAFT" && (
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(result.id)}
                          onChange={() => toggleSelection(result.id)}
                          className="rounded border-gray-300"
                        />
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {result.lot_reference || result.lot_number || `Lot #${result.lot_id}`}
                    </TableCell>
                    <TableCell className="font-medium">{result.test_type}</TableCell>
                    <TableCell>
                      {result.result_value || "-"}
                      {result.unit && (
                        <span className="text-muted-foreground ml-1">
                          {result.unit}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {result.specification || "-"}
                    </TableCell>
                    <TableCell>{getStatusBadge(result)}</TableCell>
                    <TableCell>
                      {result.status === "DRAFT" ? (
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => handleApprove(result.id)}
                            disabled={approveMutation.isPending}
                            title="Approve"
                          >
                            <CheckCircle2 className="h-4 w-4 text-green-600" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => handleReject(result.id)}
                            disabled={approveMutation.isPending}
                            title="Reject"
                          >
                            <XCircle className="h-4 w-4 text-red-600" />
                          </Button>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          {result.approved_at
                            ? new Date(result.approved_at).toLocaleDateString()
                            : "-"}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {data?.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      No test results found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {data && data.total_pages > 1 && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-muted-foreground">
                Page {data.page} of {data.total_pages}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={page === data.total_pages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
