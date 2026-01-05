import { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Loader2, Lock, AlertTriangle, FileText, Upload, X } from "lucide-react"
import { toast } from "sonner"

import { SampleModalHeader } from "./SampleModalHeader"
import { TestResultsTable, type TestResultsTableHandle } from "./TestResultsTable"
import { FilterPills } from "./FilterPills"
import { AdditionalTestsAccordion } from "./AdditionalTestsAccordion"
import { PdfUploadDropzone } from "./PdfUploadDropzone"

import { useLotWithSpecs, lotKeys, useUpdateLotStatus } from "@/hooks/useLots"
import { useTestResults, useUpdateTestResult, useCreateTestResult } from "@/hooks/useTestResults"
import { useLabTestTypes } from "@/hooks/useLabTestTypes"
import { useUploadPdf } from "@/hooks/useUploads"
import { useAuthStore } from "@/store/auth"
import { calculatePassFail } from "@/lib/spec-validation"

import type {
  Lot,
  TestResultRow,
  TestFilterStatus,
  TestSpecInProduct,
} from "@/types"

interface SampleModalProps {
  /** The lot to display, or null if closed */
  lot: Lot | null
  /** Whether the modal is open */
  isOpen: boolean
  /** Callback when the modal should close */
  onClose: () => void
  /** Callback to navigate to prev/next sample */
  onNavigate: (direction: "prev" | "next") => void
  /** Whether prev navigation is disabled */
  prevDisabled?: boolean
  /** Whether next navigation is disabled */
  nextDisabled?: boolean
}

/**
 * Sample Modal for viewing and editing test results.
 *
 * Features:
 * - Product-centric header with multi-SKU support
 * - TanStack table with smart inputs and pass/fail validation
 * - Filter pills for test status
 * - Additional tests accordion
 * - Full modal drag-and-drop PDF upload
 * - Lock banner for approved/released samples
 */
export function SampleModal({
  lot,
  isOpen,
  onClose,
  onNavigate,
  prevDisabled = false,
  nextDisabled = false,
}: SampleModalProps) {
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const scrollRef = useRef<HTMLDivElement>(null)
  const tableRef = useRef<TestResultsTableHandle>(null)
  const saveButtonRef = useRef<HTMLButtonElement>(null)

  // State
  const [filter, setFilter] = useState<TestFilterStatus>("all")
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [savingRowId, setSavingRowId] = useState<number | null>(null)
  const [rejectionReason, setRejectionReason] = useState("")
  const [showRejectDialog, setShowRejectDialog] = useState(false)
  const [showUnsavedWarning, setShowUnsavedWarning] = useState(false)
  const [showOverrideDialog, setShowOverrideDialog] = useState(false)
  const [overrideReason, setOverrideReason] = useState("")

  // Fetch lot with specs
  const { data: lotWithSpecs } = useLotWithSpecs(lot?.id ?? 0)

  // Fetch test results
  const { data: testResultsData, isLoading: isLoadingResults } = useTestResults(
    lot ? { lot_id: lot.id, page_size: 100 } : {}
  )

  // Fetch lab test types for additional tests autocomplete
  const { data: labTestTypesData } = useLabTestTypes({ page_size: 200 })

  // Mutations
  const updateTestResultMutation = useUpdateTestResult()
  const createTestResultMutation = useCreateTestResult()
  const uploadMutation = useUploadPdf()
  const updateStatusMutation = useUpdateLotStatus()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Derived state
  const isLocked = lot?.status === "approved" || lot?.status === "released"
  const isQCManagerOrAdmin = user?.role === "QC_MANAGER" || user?.role === "ADMIN"
  const canApproveReject =
    isQCManagerOrAdmin &&
    (lot?.status === "under_review" ||
      lot?.status === "awaiting_release" ||
      lot?.status === "needs_attention")
  const needsOverrideApproval = lot?.status === "needs_attention"

  // Build merged test specs from all products
  const mergedTestSpecs = useMemo(() => {
    if (!lotWithSpecs?.products) return []

    const specsMap = new Map<number, TestSpecInProduct>()
    for (const product of lotWithSpecs.products) {
      for (const spec of product.test_specifications) {
        if (!specsMap.has(spec.lab_test_type_id)) {
          specsMap.set(spec.lab_test_type_id, spec)
        }
      }
    }
    return Array.from(specsMap.values())
  }, [lotWithSpecs])

  // Transform specs + test results into rows
  // IMPORTANT: Start from specs to show ALL required tests, then merge with existing results
  const testResultRows: TestResultRow[] = useMemo(() => {
    // Build rows from specs first - these are the rows we MUST show
    const rows: TestResultRow[] = mergedTestSpecs.map((spec) => {
      // Find matching test result by test_type name
      const matchingResult = testResultsData?.items?.find(
        (r) => r.test_type === spec.test_name
      )

      if (matchingResult) {
        // Existing result - calculate pass/fail
        const passFailStatus = calculatePassFail(
          matchingResult.result_value,
          spec.specification,
          spec.test_unit
        )
        return {
          ...matchingResult,
          specificationObj: spec,
          passFailStatus,
          isFlagged: passFailStatus === "fail",
          isAdditionalTest: false,
        }
      }

      // No result yet - create placeholder row with negative ID
      return {
        id: -spec.id, // Negative ID indicates unsaved placeholder
        lot_id: lot?.id ?? 0,
        test_type: spec.test_name,
        result_value: null,
        unit: spec.test_unit,
        specification: spec.specification,
        method: spec.test_method,
        notes: null,
        test_date: null,
        pdf_source: null,
        confidence_score: null,
        status: "draft" as const,
        approved_by_id: null,
        approved_at: null,
        created_at: "",
        updated_at: null,
        specificationObj: spec,
        passFailStatus: null, // Pending - no result yet
        isFlagged: false,
        isAdditionalTest: false,
      }
    })

    // Add any additional tests (results without matching specs = ad-hoc tests)
    const additionalResults = testResultsData?.items?.filter(
      (r) => !mergedTestSpecs.some((s) => s.test_name === r.test_type)
    ) ?? []

    for (const result of additionalResults) {
      const passFailStatus = calculatePassFail(
        result.result_value,
        result.specification,
        result.unit
      )
      rows.push({
        ...result,
        specificationObj: undefined,
        passFailStatus,
        isFlagged: passFailStatus === "fail",
        isAdditionalTest: true,
      })
    }

    return rows
  }, [testResultsData, mergedTestSpecs, lot?.id])

  // Separate spec tests from additional tests
  const { specTests, additionalTests } = useMemo(() => {
    const spec: TestResultRow[] = []
    const additional: TestResultRow[] = []

    for (const row of testResultRows) {
      if (row.isAdditionalTest) {
        additional.push(row)
      } else {
        spec.push(row)
      }
    }

    return { specTests: spec, additionalTests: additional }
  }, [testResultRows])

  // Apply filter
  const filteredSpecTests = useMemo(() => {
    if (filter === "all") return specTests
    return specTests.filter((row) => {
      if (filter === "pending") return row.passFailStatus === null
      if (filter === "passed") return row.passFailStatus === "pass"
      if (filter === "failed") return row.passFailStatus === "fail"
      return true
    })
  }, [specTests, filter])

  const filteredAdditionalTests = useMemo(() => {
    if (filter === "all") return additionalTests
    return additionalTests.filter((row) => {
      if (filter === "pending") return row.passFailStatus === null
      if (filter === "passed") return row.passFailStatus === "pass"
      if (filter === "failed") return row.passFailStatus === "fail"
      return true
    })
  }, [additionalTests, filter])

  // Filter counts
  const filterCounts = useMemo(() => {
    const all = testResultRows
    return {
      all: all.length,
      pending: all.filter((r) => r.passFailStatus === null).length,
      passed: all.filter((r) => r.passFailStatus === "pass").length,
      failed: all.filter((r) => r.passFailStatus === "fail").length,
    }
  }, [testResultRows])

  // Smart scroll to first incomplete test
  useEffect(() => {
    if (isOpen && scrollRef.current && !isLoadingResults) {
      const firstIncomplete = specTests.find((r) => r.passFailStatus === null)
      if (firstIncomplete) {
        // Scroll to first incomplete - for now just scroll to top
        scrollRef.current.scrollTop = 0
      }
    }
  }, [isOpen, isLoadingResults, specTests])

  // Handle updating a test result (or creating new one for placeholder rows)
  const handleUpdateResult = useCallback(
    async (id: number, field: string, value: string) => {
      setSavingRowId(id)
      try {
        if (id < 0) {
          // Placeholder row (negative ID) - need to CREATE a new TestResult
          const spec = mergedTestSpecs.find((s) => s.id === -id)
          if (spec && lot) {
            await createTestResultMutation.mutateAsync({
              lot_id: lot.id,
              test_type: spec.test_name,
              [field]: value,
              unit: spec.test_unit ?? undefined,
              specification: spec.specification ?? undefined,
              method: spec.test_method ?? undefined,
            })
          }
        } else {
          // Existing row - UPDATE
          await updateTestResultMutation.mutateAsync({
            id,
            data: { [field]: value },
          })
        }
        // Invalidate queries to refresh status
        queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
        queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
      } catch (error) {
        toast.error("Failed to save", {
          description: "Please try again",
        })
      } finally {
        setSavingRowId(null)
      }
    },
    [updateTestResultMutation, createTestResultMutation, mergedTestSpecs, lot, queryClient]
  )

  // Handle adding a new ad-hoc test
  const handleAddTest = useCallback(
    async (testName: string, _labTestTypeId: number) => {
      if (!lot) return
      try {
        await createTestResultMutation.mutateAsync({
          lot_id: lot.id,
          test_type: testName,
          result_value: undefined,
          unit: undefined,
        })
        toast.success("Test added")
      } catch (error) {
        toast.error("Failed to add test")
      }
    },
    [lot, createTestResultMutation]
  )

  // Drag and drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.dataTransfer.types.includes("Files")) {
      setIsDragging(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    if (
      e.clientX < rect.left ||
      e.clientX >= rect.right ||
      e.clientY < rect.top ||
      e.clientY >= rect.bottom
    ) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)

      const files = Array.from(e.dataTransfer.files)
      const pdfFile = files.find((f) => f.type === "application/pdf")

      if (!pdfFile) {
        setUploadError("Only PDF files are allowed")
        return
      }

      if (pdfFile.size > 10 * 1024 * 1024) {
        setUploadError("File size must be less than 10MB")
        return
      }

      setIsUploading(true)
      setUploadError(null)

      try {
        await uploadMutation.mutateAsync(pdfFile)
        toast.success("PDF uploaded successfully")
      } catch (error) {
        setUploadError("Failed to upload file")
      } finally {
        setIsUploading(false)
      }
    },
    [uploadMutation]
  )

  // Handle file input change
  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return

      if (file.type !== "application/pdf") {
        setUploadError("Only PDF files are allowed")
        return
      }

      if (file.size > 10 * 1024 * 1024) {
        setUploadError("File size must be less than 10MB")
        return
      }

      setIsUploading(true)
      setUploadError(null)

      try {
        await uploadMutation.mutateAsync(file)
        toast.success("PDF uploaded successfully")
      } catch (error) {
        setUploadError("Failed to upload file")
      } finally {
        setIsUploading(false)
        if (fileInputRef.current) {
          fileInputRef.current.value = ""
        }
      }
    },
    [uploadMutation]
  )

  // Handle approve (or show override dialog for needs_attention)
  const handleApprove = useCallback(async () => {
    if (!lot) return

    // If in needs_attention status, show override dialog first
    if (needsOverrideApproval) {
      setShowOverrideDialog(true)
      return
    }

    try {
      await updateStatusMutation.mutateAsync({ id: lot.id, status: "approved" })
      toast.success("Sample approved")
    } catch (error) {
      toast.error("Failed to approve")
    }
  }, [lot, updateStatusMutation, needsOverrideApproval])

  // Handle override approval (for needs_attention status)
  const handleOverrideApprove = useCallback(async () => {
    if (!lot || !overrideReason.trim()) return
    try {
      await updateStatusMutation.mutateAsync({
        id: lot.id,
        status: "approved",
        overrideReason: overrideReason.trim(),
      })
      setShowOverrideDialog(false)
      setOverrideReason("")
      toast.success("Sample approved with override")
    } catch (error) {
      toast.error("Failed to approve")
    }
  }, [lot, overrideReason, updateStatusMutation])

  // Handle reject
  const handleReject = useCallback(async () => {
    if (!lot || !rejectionReason.trim()) return
    try {
      await updateStatusMutation.mutateAsync({
        id: lot.id,
        status: "rejected",
        rejectionReason: rejectionReason.trim(),
      })
      setShowRejectDialog(false)
      setRejectionReason("")
      toast.success("Sample rejected")
    } catch (error) {
      toast.error("Failed to reject")
    }
  }, [lot, rejectionReason, updateStatusMutation])

  // Handle modal close attempt (check for unsaved changes)
  const handleCloseAttempt = useCallback(() => {
    // Check if table has unsaved changes
    if (tableRef.current?.hasUnsavedChanges()) {
      setShowUnsavedWarning(true)
      return
    }
    onClose()
  }, [onClose])

  // Force close (discard changes)
  const handleForceClose = useCallback(() => {
    setShowUnsavedWarning(false)
    onClose()
  }, [onClose])

  if (!lot) return null

  // Get attached PDFs from test results
  const attachedPdfs = Array.from(
    new Set(
      testResultRows
        .filter((tr) => tr.pdf_source)
        .map((tr) => tr.pdf_source as string)
    )
  )

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleCloseAttempt()}>
      <DialogContent
        className="sm:max-w-6xl max-h-[90vh] overflow-hidden flex flex-col"
        showCloseButton={false}
        onDragEnter={handleDragEnter}
        onKeyDown={(e) => {
          // Handle Escape key with unsaved changes check
          if (e.key === "Escape") {
            e.preventDefault()
            handleCloseAttempt()
          }
        }}
      >
        {/* Drag-drop overlay */}
        <PdfUploadDropzone
          isDragging={isDragging}
          isUploading={isUploading}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        />

        {/* Lock banner for approved/released */}
        {isLocked && (
          <div className="flex items-center gap-2 px-4 py-2 bg-slate-100 border-b border-slate-200 text-sm text-slate-600">
            <Lock className="h-4 w-4" />
            This sample is locked and cannot be edited.
          </div>
        )}

        {/* Header */}
        {lotWithSpecs ? (
          <SampleModalHeader
            lot={lotWithSpecs}
            isLocked={isLocked}
            prevDisabled={prevDisabled}
            nextDisabled={nextDisabled}
            onNavigate={onNavigate}
            onClose={handleCloseAttempt}
          />
        ) : (
          <div className="h-20 flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        )}

        {/* Rejection banner */}
        {lot.status === "rejected" && lot.rejection_reason && (
          <div className="mx-6 mt-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
            <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-500" />
            <div>
              <p className="text-sm font-medium text-red-800">Rejection Reason</p>
              <p className="mt-1 text-sm text-red-700">{lot.rejection_reason}</p>
            </div>
          </div>
        )}

        {/* Scrollable content */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4">
          {isLoadingResults ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
            </div>
          ) : (
            <>
              {/* Filter pills */}
              <FilterPills
                filter={filter}
                counts={filterCounts}
                onChange={setFilter}
                className="mb-4"
              />

              {/* Test Results section */}
              <div className="mb-2">
                <h3 className="text-sm font-semibold text-slate-900 mb-3">
                  Test Results ({filterCounts.passed + filterCounts.failed} of{" "}
                  {filterCounts.all} complete)
                </h3>
                <TestResultsTable
                  ref={tableRef}
                  testResults={filteredSpecTests}
                  productSpecs={mergedTestSpecs}
                  onUpdateResult={handleUpdateResult}
                  disabled={isLocked}
                  savingRowId={savingRowId}
                  saveButtonRef={saveButtonRef}
                />
              </div>

              {/* Additional Tests accordion */}
              <AdditionalTestsAccordion
                additionalTests={filteredAdditionalTests}
                labTestTypes={labTestTypesData?.items || []}
                onUpdateResult={handleUpdateResult}
                onAddTest={handleAddTest}
                disabled={isLocked}
                savingRowId={savingRowId}
              />

              {/* Attached PDFs section */}
              <div className="mt-6">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-slate-900">
                    Attached PDFs
                  </h3>
                  {!isLocked && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                    >
                      <Upload className="h-3.5 w-3.5 mr-1.5" />
                      Upload PDF
                    </Button>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </div>

                {uploadError && (
                  <div className="mb-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-md px-3 py-2">
                    <X className="h-4 w-4" />
                    {uploadError}
                  </div>
                )}

                {attachedPdfs.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {attachedPdfs.map((pdf, idx) => (
                      <div
                        key={idx}
                        className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5"
                      >
                        <FileText className="h-4 w-4 text-slate-400" />
                        <span className="text-sm text-slate-600">{pdf}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">
                    No PDFs attached. Drag and drop or click upload.
                  </p>
                )}
              </div>
            </>
          )}
        </div>

        {/* Rejection dialog */}
        {showRejectDialog && (
          <div className="mx-6 mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm font-medium text-red-800 mb-2">
              Please provide a rejection reason:
            </p>
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="Enter reason for rejection..."
              className="w-full h-24 px-3 py-2 text-sm border border-red-200 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500"
            />
            <div className="flex justify-end gap-2 mt-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowRejectDialog(false)
                  setRejectionReason("")
                }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={handleReject}
                disabled={!rejectionReason.trim() || updateStatusMutation.isPending}
              >
                {updateStatusMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Confirm Rejection"
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Unsaved changes warning dialog */}
        {showUnsavedWarning && (
          <div className="mx-6 mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 flex-shrink-0 text-amber-500" />
              <div className="flex-1">
                <p className="text-sm font-medium text-amber-800">
                  You have unsaved changes
                </p>
                <p className="mt-1 text-sm text-amber-700">
                  Are you sure you want to close? Your changes will be lost.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowUnsavedWarning(false)}
              >
                Keep Editing
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={handleForceClose}
              >
                Discard Changes
              </Button>
            </div>
          </div>
        )}

        {/* Override approval dialog (for needs_attention status) */}
        {showOverrideDialog && (
          <div className="mx-6 mb-4 p-4 bg-orange-50 border border-orange-200 rounded-lg">
            <div className="flex items-start gap-3 mb-3">
              <AlertTriangle className="h-5 w-5 flex-shrink-0 text-orange-500" />
              <div>
                <p className="text-sm font-medium text-orange-800">
                  QC Override Required
                </p>
                <p className="mt-1 text-sm text-orange-700">
                  This sample has failing tests. Please provide a justification
                  for approving despite the failures.
                </p>
              </div>
            </div>
            <textarea
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="Enter justification for override approval..."
              className="w-full h-24 px-3 py-2 text-sm border border-orange-200 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
            <div className="flex justify-end gap-2 mt-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowOverrideDialog(false)
                  setOverrideReason("")
                }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleOverrideApprove}
                disabled={!overrideReason.trim() || updateStatusMutation.isPending}
                className="bg-orange-600 hover:bg-orange-700"
              >
                {updateStatusMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Approve with Override"
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Footer */}
        <DialogFooter className="flex-shrink-0 border-t border-slate-200 px-6 py-4">
          <div className="flex w-full items-center justify-end gap-2">
            {/* QC actions */}
            {canApproveReject && !showRejectDialog && (
              <>
                <Button
                  variant="outline"
                  onClick={() => setShowRejectDialog(true)}
                  className="text-red-600 border-red-200 hover:bg-red-50"
                >
                  Reject
                </Button>
                <Button
                  onClick={handleApprove}
                  disabled={updateStatusMutation.isPending}
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  {updateStatusMutation.isPending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : null}
                  Approve
                </Button>
              </>
            )}

            {/* Save/Close button */}
            <Button ref={saveButtonRef} onClick={handleCloseAttempt}>
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Re-export for convenience
export { SampleModalHeader } from "./SampleModalHeader"
export { TestResultsTable } from "./TestResultsTable"
export { FilterPills } from "./FilterPills"
export { AdditionalTestsAccordion } from "./AdditionalTestsAccordion"
export { PdfUploadDropzone } from "./PdfUploadDropzone"
export { PassFailBadge } from "./PassFailBadge"
export { SmartResultInput } from "./SmartResultInput"
