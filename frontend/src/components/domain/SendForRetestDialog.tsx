/**
 * Send for Retest Dialog
 *
 * Allows QC Manager/Admin to request a retest of specific tests when a suspected
 * false positive is detected. Creates a retest request with an -R1 reference number
 * for lab communication and provides PDF and Daane COC downloads.
 */

import { useState, useCallback, useMemo, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Loader2, RefreshCw, Download, CheckCircle2, Check, AlertTriangle } from "lucide-react"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import { useCreateRetestRequest, useDownloadRetestPdf, useRetestRequests } from "@/hooks/useRetests"
import { useDownloadRetestDaaneCoc, useDownloadRetestDaaneCocPdf } from "@/hooks/useDaaneCoc"
import { PassFailBadge } from "@/components/domain/SampleModal/PassFailBadge"
import type { TestResultRow, RetestRequest } from "@/types"

interface SendForRetestDialogProps {
  /** Whether the dialog is open */
  isOpen: boolean
  /** Callback when the dialog should close */
  onClose: () => void
  /** The lot ID to create retest request for */
  lotId: number
  /** All test result rows for the lot */
  testResults: TestResultRow[]
  /** Default text for special instructions (auto-populated from product serving size) */
  defaultSpecialInstructions?: string
  /** Callback when retest request is successfully created */
  onSuccess?: () => void
  /** Callback when user clicks Done on success screen (closes both dialogs) */
  onComplete?: () => void
}

type DialogState = "select" | "confirm" | "success"

export function SendForRetestDialog({
  isOpen,
  onClose,
  lotId,
  testResults,
  defaultSpecialInstructions,
  onSuccess,
  onComplete,
}: SendForRetestDialogProps) {
  // Dialog state
  const [dialogState, setDialogState] = useState<DialogState>("select")
  const [selectedTestIds, setSelectedTestIds] = useState<Set<number>>(new Set())
  const [reason, setReason] = useState("")
  const [createdRequest, setCreatedRequest] = useState<RetestRequest | null>(null)
  const [specialInstructions, setSpecialInstructions] = useState("")

  // Mutations
  const createRetestMutation = useCreateRetestRequest()
  const downloadPdfMutation = useDownloadRetestPdf()
  const downloadCocMutation = useDownloadRetestDaaneCoc()
  const downloadCocPdfMutation = useDownloadRetestDaaneCocPdf()

  // Fetch existing retest requests for this lot to check for duplicates
  const { data: retestData } = useRetestRequests(lotId)

  // Build a set of test_result_ids that already have pending or review_required retests
  const testIdsWithPendingRetest = useMemo(() => {
    const pending = new Set<number>()
    if (retestData?.items) {
      for (const request of retestData.items) {
        if (request.status === "pending" || request.status === "review_required") {
          for (const item of request.items) {
            pending.add(item.test_result_id)
          }
        }
      }
    }
    return pending
  }, [retestData])

  // Filter to only tests that have actual results (positive IDs)
  const testsWithResults = useMemo(() => {
    return testResults.filter((t) => t.id > 0 && t.result_value !== null)
  }, [testResults])

  // Compute why the button is disabled (for tooltip)
  const disabledReason = useMemo(() => {
    if (selectedTestIds.size === 0) {
      return "Select at least one test to retest"
    }
    if (!reason.trim()) {
      return "Enter a reason for the retest"
    }
    return null
  }, [selectedTestIds.size, reason])

  // Compute which selected tests already have pending retests
  const selectedTestsWithPendingRetest = useMemo(() => {
    return testsWithResults.filter(
      (t) => selectedTestIds.has(t.id) && testIdsWithPendingRetest.has(t.id)
    )
  }, [testsWithResults, selectedTestIds, testIdsWithPendingRetest])

  // Auto-select failing tests when dialog opens
  // Using useEffect ensures testsWithResults is populated before we filter
  useEffect(() => {
    if (isOpen && testsWithResults.length > 0 && dialogState !== "success" && dialogState !== "confirm") {
      // Pre-select failing tests
      const failingIds = new Set(
        testsWithResults
          .filter((t) => t.passFailStatus === "fail")
          .map((t) => t.id)
      )
      setSelectedTestIds(failingIds)
      // Reset dialog state for fresh open
      setDialogState("select")
      setReason("")
      setCreatedRequest(null)
      setSpecialInstructions(defaultSpecialInstructions ?? "(NO SERVING SIZE DETERMINED)")
    }
  }, [isOpen, testsWithResults, dialogState, defaultSpecialInstructions])

  // Simplified handleOpenChange - only handles close
  const handleOpenChange = useCallback(
    (open: boolean) => {
      if (!open) {
        onClose()
      }
    },
    [onClose]
  )

  // Toggle test selection
  const toggleTest = useCallback((testId: number) => {
    setSelectedTestIds((prev) => {
      const next = new Set(prev)
      if (next.has(testId)) {
        next.delete(testId)
      } else {
        next.add(testId)
      }
      return next
    })
  }, [])

  // Actually create the retest request (called directly or after confirmation)
  const executeCreateRequest = useCallback(async () => {
    try {
      const request = await createRetestMutation.mutateAsync({
        lotId,
        data: {
          test_result_ids: Array.from(selectedTestIds),
          reason: reason.trim(),
        },
      })
      setCreatedRequest(request)
      setDialogState("success")
      toast.success("Retest request created")
      if (onSuccess) {
        onSuccess()
      }
    } catch (error) {
      console.error("Failed to create retest request:", error)
      toast.error("Failed to create retest request")
    }
  }, [selectedTestIds, reason, lotId, createRetestMutation, onSuccess])

  // Create retest request (with duplicate check)
  const handleCreateRequest = useCallback(async () => {
    if (selectedTestIds.size === 0) {
      toast.error("Please select at least one test")
      return
    }
    if (!reason.trim()) {
      toast.error("Please provide a reason for the retest")
      return
    }

    // Check for duplicates - show confirmation if any selected tests have pending retests
    if (selectedTestsWithPendingRetest.length > 0) {
      setDialogState("confirm")
      return
    }

    // No duplicates - proceed directly
    await executeCreateRequest()
  }, [selectedTestIds, reason, selectedTestsWithPendingRetest, executeCreateRequest])

  // Download PDF
  const handleDownloadPdf = useCallback(async () => {
    if (!createdRequest) return
    try {
      await downloadPdfMutation.mutateAsync(createdRequest.id)
      toast.success("PDF downloaded")
    } catch (error) {
      console.error("Failed to download PDF:", error)
      toast.error("Failed to download PDF")
    }
  }, [createdRequest, downloadPdfMutation])

  const handleDownloadCoc = useCallback(async () => {
    if (!createdRequest) return
    try {
      const result = await downloadCocMutation.mutateAsync(createdRequest.id)
      toast.success("Daane COC (XLSX) downloaded")
      if (result.limitExceeded) {
        toast.warning(`Daane COC supports ${result.testLimit} tests. ${result.testCount} tests found; only the first ${result.testLimit} were included.`)
      }
    } catch (error) {
      console.error("Failed to download Daane COC:", error)
      toast.error("Failed to download Daane COC")
    }
  }, [createdRequest, downloadCocMutation])

  const handleDownloadCocPdf = useCallback(async () => {
    if (!createdRequest) return
    try {
      const result = await downloadCocPdfMutation.mutateAsync({
        requestId: createdRequest.id,
        specialInstructions: specialInstructions,
      })
      toast.success("Daane COC (PDF) downloaded")
      if (result.limitExceeded) {
        toast.warning(`Daane COC supports ${result.testLimit} tests. ${result.testCount} tests found; only the first ${result.testLimit} were included.`)
      }
    } catch (error) {
      console.error("Failed to download Daane COC PDF:", error)
      toast.error("Failed to download Daane COC PDF")
    }
  }, [createdRequest, downloadCocPdfMutation, specialInstructions])

  // Render selection state
  const renderSelectState = () => (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-amber-700">
          <RefreshCw className="h-5 w-5" />
          Send for Retest
        </DialogTitle>
        <DialogDescription>
          Select the tests that need to be retested and provide a reason.
        </DialogDescription>
      </DialogHeader>

      <div className="py-4 space-y-4">
        {/* Test selection table */}
        <div>
          <Label className="text-sm font-medium text-slate-700 mb-2 block">
            Select tests to retest:
          </Label>
          <div className="border rounded-lg overflow-hidden max-h-64 overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead className="w-10"></TableHead>
                  <TableHead>Test</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead>Spec</TableHead>
                  <TableHead className="w-20">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {testsWithResults.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-slate-500 py-8">
                      No test results available
                    </TableCell>
                  </TableRow>
                ) : (
                  testsWithResults.map((test) => {
                    const isFailing = test.passFailStatus === "fail"
                    const isSelected = selectedTestIds.has(test.id)
                    const hasPendingRetest = testIdsWithPendingRetest.has(test.id)
                    return (
                      <TableRow
                        key={test.id}
                        className={`cursor-pointer transition-colors ${
                          isFailing ? "bg-red-50/50" : ""
                        } ${isSelected ? "bg-amber-50" : ""}`}
                        onClick={() => toggleTest(test.id)}
                      >
                        <TableCell>
                          <Checkbox
                            checked={isSelected}
                            onCheckedChange={() => toggleTest(test.id)}
                          />
                        </TableCell>
                        <TableCell className="font-medium text-slate-900">
                          <div className="flex items-center gap-2">
                            {test.test_type}
                            {hasPendingRetest && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700" title="Already has a pending retest">
                                <AlertTriangle className="h-3 w-3" />
                                Pending
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-slate-600">
                          {test.result_value || "-"}
                        </TableCell>
                        <TableCell className="text-slate-600">
                          {test.specification || test.specificationObj?.specification || "-"}
                        </TableCell>
                        <TableCell>
                          <PassFailBadge status={test.passFailStatus} />
                        </TableCell>
                      </TableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {selectedTestIds.size} test{selectedTestIds.size !== 1 ? "s" : ""} selected
          </p>
        </div>

        {/* Reason input */}
        <div>
          <Label htmlFor="retest-reason" className="text-sm font-medium text-slate-700">
            Reason for retest <span className="text-red-500">*</span>
          </Label>
          <Textarea
            id="retest-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain why retest is needed (e.g., suspected lab contamination, values inconsistent with previous batches...)"
            className={cn(
              "mt-1.5 min-h-[80px] resize-none",
              selectedTestIds.size > 0 && !reason.trim() && "ring-2 ring-amber-400 border-amber-400"
            )}
          />
          {selectedTestIds.size > 0 && !reason.trim() && (
            <p className="mt-1 text-xs text-amber-600">
              Please provide a reason to enable submission
            </p>
          )}
        </div>

        {/* Special instructions */}
        <div>
          <Label className="text-sm font-medium text-slate-700 mb-1.5 block">
            Special Instructions
          </Label>
          <Textarea
            value={specialInstructions}
            onChange={(e) => setSpecialInstructions(e.target.value)}
            placeholder="e.g., Serving Size = 30g"
            className="min-h-[60px] resize-none text-sm"
          />
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <TooltipProvider>
          <Tooltip open={disabledReason ? undefined : false}>
            <TooltipTrigger asChild>
              <span className={disabledReason ? "cursor-not-allowed" : ""}>
                <Button
                  onClick={handleCreateRequest}
                  disabled={
                    createRetestMutation.isPending ||
                    selectedTestIds.size === 0 ||
                    !reason.trim()
                  }
                  className="bg-amber-600 hover:bg-amber-700 disabled:pointer-events-none"
                >
                  {createRetestMutation.isPending && (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  )}
                  Create Request
                </Button>
              </span>
            </TooltipTrigger>
            {disabledReason && (
              <TooltipContent side="top">
                <p>{disabledReason}</p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </DialogFooter>
    </>
  )

  // Render success state
  const renderSuccessState = () => {
    if (!createdRequest) return null

    return (
      <>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-600">
            <CheckCircle2 className="h-5 w-5" />
            Retest Request Created
          </DialogTitle>
        </DialogHeader>

        <div className="py-4 space-y-5">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Retest Reference</p>
              <p className="text-xl font-mono font-semibold text-slate-900">
                {createdRequest.reference_number}
              </p>
            </div>
            <Check className="h-5 w-5 text-emerald-500" />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h4 className="text-xs uppercase tracking-wide text-slate-500 mb-2">Tests to Retest</h4>
              <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
                {createdRequest.items.map((item) => (
                  <li key={item.id}>{item.test_type}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h4 className="text-xs uppercase tracking-wide text-slate-500 mb-2">Reason</h4>
              <p className="text-sm text-slate-700">{createdRequest.reason}</p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-3">Downloads</p>
            <div className="flex flex-col sm:flex-row gap-2">
              <Button
                variant="outline"
                onClick={handleDownloadPdf}
                disabled={downloadPdfMutation.isPending}
                className="border-slate-200 w-full sm:w-auto"
              >
                {downloadPdfMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Download className="h-4 w-4 mr-2" />
                )}
                Download PDF
              </Button>
              <Button
                variant="outline"
                onClick={handleDownloadCoc}
                disabled={downloadCocMutation.isPending}
                className="border-slate-200 w-full sm:w-auto"
              >
                {downloadCocMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Download className="h-4 w-4 mr-2" />
                )}
                Download Daane XLSX
              </Button>
              <Button
                variant="outline"
                onClick={handleDownloadCocPdf}
                disabled={downloadCocPdfMutation.isPending}
                className="border-slate-200 w-full sm:w-auto"
              >
                {downloadCocPdfMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Download className="h-4 w-4 mr-2" />
                )}
                Download Daane PDF
              </Button>
            </div>
          </div>
        </div>

        <DialogFooter className="flex-col sm:flex-row sm:justify-end gap-2">
          <Button
            variant="outline"
            className="border-slate-200 w-full sm:w-auto"
            onClick={() => {
              if (onComplete) {
                onComplete()
              } else {
                onClose()
              }
            }}
          >
            Done
          </Button>
        </DialogFooter>
      </>
    )
  }

  // Render confirmation state for duplicate retests
  const renderConfirmState = () => (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-amber-700">
          <AlertTriangle className="h-5 w-5" />
          Duplicate Retest Warning
        </DialogTitle>
        <DialogDescription>
          Some selected tests already have pending retests.
        </DialogDescription>
      </DialogHeader>

      <div className="py-4 space-y-4">
        <p className="text-sm text-slate-600">
          The following test{selectedTestsWithPendingRetest.length > 1 ? "s" : ""} already{" "}
          {selectedTestsWithPendingRetest.length > 1 ? "have" : "has"} a pending retest request:
        </p>
        <ul className="list-disc list-inside text-sm text-amber-700 space-y-1 bg-amber-50 rounded-lg p-3">
          {selectedTestsWithPendingRetest.map((test) => (
            <li key={test.id} className="font-medium">{test.test_type}</li>
          ))}
        </ul>
        <p className="text-sm text-slate-600">
          Creating another retest request for these tests may cause confusion at the lab.
          Are you sure you want to proceed?
        </p>
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={() => setDialogState("select")}>
          Go Back
        </Button>
        <Button
          onClick={executeCreateRequest}
          disabled={createRetestMutation.isPending}
          className="bg-amber-600 hover:bg-amber-700"
        >
          {createRetestMutation.isPending && (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          )}
          Create Anyway
        </Button>
      </DialogFooter>
    </>
  )

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        {dialogState === "select" && renderSelectState()}
        {dialogState === "confirm" && renderConfirmState()}
        {dialogState === "success" && renderSuccessState()}
      </DialogContent>
    </Dialog>
  )
}

export default SendForRetestDialog
