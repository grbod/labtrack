import { useState, useEffect, useMemo, useCallback, useRef } from "react"
import type { KeyboardEvent } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useDropzone } from "react-dropzone"
import { useNavigate } from "react-router-dom"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Loader2, Lock, AlertTriangle, FileText, Upload, X, ExternalLink, ShieldAlert, CheckCircle2, RefreshCw } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import SimpleBar from "simplebar-react"
import "simplebar-react/dist/simplebar.min.css"

import { SampleModalHeader } from "./SampleModalHeader"
import { TestResultsTable, type TestResultsTableHandle } from "./TestResultsTable"
import { FilterPills } from "./FilterPills"
import { AdditionalTestsAccordion } from "./AdditionalTestsAccordion"
import { RetestsHistoryAccordion } from "./RetestsHistoryAccordion"
import { useLotWithSpecs, lotKeys, useSubmitForReview } from "@/hooks/useLots"
import { useTestResults, useUpdateTestResult, useCreateTestResult, useDeleteTestResult } from "@/hooks/useTestResults"
import { useRetestRequests } from "@/hooks/useRetests"
import { useLabTestTypes } from "@/hooks/useLabTestTypes"
import { useUploadPdf } from "@/hooks/useUploads"
import { uploadsApi } from "@/api/uploads"
import { authApi } from "@/api/client"
import { useLabInfo } from "@/hooks/useLabInfo"
import { useAuthStore } from "@/store/auth"
import { calculatePassFail } from "@/lib/spec-validation"
import { SendForRetestDialog } from "@/components/domain/SendForRetestDialog"

import type {
  Lot,
  LotStatus,
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
  /** Callback when sample is successfully submitted for approval */
  onSubmitSuccess?: () => void
  /** Whether to auto-scroll to Retests History accordion on open */
  scrollToRetests?: boolean
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
  onSubmitSuccess,
  scrollToRetests = false,
}: SampleModalProps) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const scrollRef = useRef<HTMLDivElement>(null)
  const tableRef = useRef<TestResultsTableHandle>(null)
  const retestsRef = useRef<HTMLDivElement>(null)
  const saveButtonRef = useRef<HTMLButtonElement>(null)
  const additionalTriggerRef = useRef<HTMLButtonElement>(null)
  const addTestButtonRef = useRef<HTMLButtonElement>(null)
  const uploadButtonRef = useRef<HTMLButtonElement>(null)

  // Auth store for role-based UI
  const { user } = useAuthStore()
  const canGoToRelease = user?.role === "admin" || user?.role === "qc_manager"
  const canRequestRetest = user?.role === "admin" || user?.role === "qc_manager"

  // State
  const [filter, setFilter] = useState<TestFilterStatus>("all")
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [savingRowId, setSavingRowId] = useState<number | null>(null)
  const [showUnsavedWarning, setShowUnsavedWarning] = useState(false)

  // Success dialog state after submit for approval
  const [showSubmitSuccessDialog, setShowSubmitSuccessDialog] = useState(false)
  const [submittedLotRef, setSubmittedLotRef] = useState<string | null>(null)

  // Retest dialog state
  const [showRetestDialog, setShowRetestDialog] = useState(false)
  const [isAdditionalExpanded, setIsAdditionalExpanded] = useState(false)
  const [openedFromStatus, setOpenedFromStatus] = useState<LotStatus | null>(null)
  const openedFromLotIdRef = useRef<number | null>(null)

  // Override modal state
  const [showOverrideModal, setShowOverrideModal] = useState(false)
  const [overrideUsername, setOverrideUsername] = useState("")
  const [overridePassword, setOverridePassword] = useState("")
  const [overrideError, setOverrideError] = useState<string | null>(null)
  const [isVerifyingOverride, setIsVerifyingOverride] = useState(false)

  // Focus helpers for custom tab order
  const focusSaveButton = useCallback(() => {
    saveButtonRef.current?.focus()
  }, [])

  const focusUploadButton = useCallback(() => {
    if (uploadButtonRef.current) {
      uploadButtonRef.current.focus()
      return true
    }
    focusSaveButton()
    return false
  }, [focusSaveButton])

  const focusAdditionalTrigger = useCallback(() => {
    if (additionalTriggerRef.current) {
      additionalTriggerRef.current.focus()
      return true
    }
    return false
  }, [])

  const focusAddTestButton = useCallback(() => {
    if (addTestButtonRef.current) {
      addTestButtonRef.current.focus()
      return true
    }
    return false
  }, [])

  const focusFirstResultCell = useCallback(() => {
    tableRef.current?.focusFirstCell()
  }, [])

  const focusLastResultCell = useCallback(() => {
    tableRef.current?.focusLastCell()
  }, [])

  const handleMainTableFocusExit = useCallback((direction: "forward" | "backward") => {
    if (direction === "forward") {
      if (!focusAdditionalTrigger()) {
        focusUploadButton()
      }
    } else {
      focusSaveButton()
    }
  }, [focusAdditionalTrigger, focusUploadButton, focusSaveButton])

  const handleAdditionalTriggerKeyDown = useCallback((event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== "Tab") return
    event.preventDefault()
    event.stopPropagation()
    if (event.shiftKey) {
      focusLastResultCell()
      return
    }
    if (isAdditionalExpanded && focusAddTestButton()) {
      return
    }
    focusUploadButton()
  }, [focusAddTestButton, focusLastResultCell, focusUploadButton, isAdditionalExpanded])

  const handleAddTestKeyDown = useCallback((event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== "Tab") return
    event.preventDefault()
    event.stopPropagation()
    if (event.shiftKey) {
      if (!focusAdditionalTrigger()) {
        focusLastResultCell()
      }
    } else {
      focusUploadButton()
    }
  }, [focusAdditionalTrigger, focusLastResultCell, focusUploadButton])

  const handleUploadKeyDown = useCallback((event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== "Tab") return
    event.preventDefault()
    event.stopPropagation()
    if (event.shiftKey) {
      if (isAdditionalExpanded && focusAddTestButton()) {
        return
      }
      if (focusAdditionalTrigger()) {
        return
      }
      focusLastResultCell()
    } else {
      focusSaveButton()
    }
  }, [focusAddTestButton, focusAdditionalTrigger, focusLastResultCell, focusSaveButton, isAdditionalExpanded])

  const handleSaveButtonKeyDown = useCallback((event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== "Tab") return
    event.preventDefault()
    event.stopPropagation()
    if (event.shiftKey) {
      if (focusUploadButton()) {
        return
      }
      if (focusAdditionalTrigger()) {
        return
      }
      focusLastResultCell()
    } else {
      focusFirstResultCell()
    }
  }, [focusAdditionalTrigger, focusFirstResultCell, focusLastResultCell, focusUploadButton])

  // Fetch lot with specs
  const { data: lotWithSpecs } = useLotWithSpecs(lot?.id ?? 0)

  // Fetch test results
  const { data: testResultsData, isLoading: isLoadingResults } = useTestResults(
    lot ? { lot_id: lot.id, page_size: 100 } : {}
  )

  // Fetch lab test types for additional tests autocomplete
  const { data: labTestTypesData } = useLabTestTypes({ page_size: 200 })

  // Fetch retest requests for original value display
  const { data: retestData } = useRetestRequests(lot?.id ?? 0)

  // Build map of test_result_id -> original_value from retest items
  const originalValuesMap = useMemo(() => {
    const map = new Map<number, string | null>()
    if (retestData?.items) {
      for (const request of retestData.items) {
        for (const item of request.items) {
          // Only show original value if the test was retested (value changed)
          // Keep the most recent original value if retested multiple times
          if (!map.has(item.test_result_id)) {
            map.set(item.test_result_id, item.original_value)
          }
        }
      }
    }
    return map
  }, [retestData])

  // Mutations
  const updateTestResultMutation = useUpdateTestResult()
  const createTestResultMutation = useCreateTestResult()
  const deleteTestResultMutation = useDeleteTestResult()
  const uploadMutation = useUploadPdf()
  const submitForReviewMutation = useSubmitForReview()

  // Lab info for PDF requirement setting
  const { labInfo } = useLabInfo()

  // Snapshot status when modal opens or lot changes (prevents auto-updates from enabling actions mid-session)
  useEffect(() => {
    if (!isOpen) {
      openedFromLotIdRef.current = null
      setOpenedFromStatus(null)
      return
    }
    if (!lot) {
      setOpenedFromStatus(null)
      return
    }
    if (openedFromLotIdRef.current !== lot.id) {
      openedFromLotIdRef.current = lot.id
      setOpenedFromStatus(lot.status)
    }
  }, [isOpen, lot?.id, lot?.status])

  // Derived state - use lotWithSpecs status if available (fresh data), fallback to lot prop
  const currentStatus = lotWithSpecs?.status ?? lot?.status
  const isLocked = currentStatus === "approved" || currentStatus === "released"
  const openedFromUnderReview = openedFromStatus === "under_review"

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

  // Check if there are any failing tests (for retest button visibility)
  const hasFailingTests = useMemo(() => {
    return testResultRows.some((r) => r.passFailStatus === "fail")
  }, [testResultRows])

  const allTestsPassing = useMemo(() => {
    if (testResultRows.length === 0) return false
    return testResultRows.every((r) => r.passFailStatus === "pass")
  }, [testResultRows])

  const canSubmitForReview =
    openedFromUnderReview &&
    currentStatus === "under_review" &&
    allTestsPassing

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

  // Keyboard navigation: left/right arrows to navigate between samples
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't navigate if user is typing in an input, textarea, or contenteditable
      const target = e.target as HTMLElement
      const isInputFocused =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable

      if (isInputFocused) return

      if (e.key === "ArrowLeft" && !prevDisabled) {
        e.preventDefault()
        onNavigate("prev")
      } else if (e.key === "ArrowRight" && !nextDisabled) {
        e.preventDefault()
        onNavigate("next")
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [isOpen, prevDisabled, nextDisabled, onNavigate])

  // Auto-scroll to retests section when requested
  useEffect(() => {
    if (scrollToRetests && isOpen && retestsRef.current) {
      const timer = setTimeout(() => {
        retestsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 150)
      return () => clearTimeout(timer)
    }
  }, [scrollToRetests, isOpen])

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
        // Refresh queries to update status immediately
        queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
        queryClient.invalidateQueries({ queryKey: lotKeys.statusCounts() })
        if (lot) {
          // Force immediate refetch of lot details so modal shows updated status
          await queryClient.refetchQueries({ queryKey: lotKeys.detailWithSpecs(lot.id) })
        }
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

  // Handle deleting an ad-hoc test
  const handleDeleteResult = useCallback(
    async (id: number) => {
      try {
        await deleteTestResultMutation.mutateAsync(id)
        toast.success("Test removed")
      } catch (error) {
        toast.error("Failed to remove test")
      }
    },
    [deleteTestResultMutation]
  )

  // Dropzone handler using react-dropzone
  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return

      // Check file sizes
      const oversizedFiles = acceptedFiles.filter(f => f.size > 10 * 1024 * 1024)
      if (oversizedFiles.length > 0) {
        setUploadError(`${oversizedFiles.length} file(s) exceed 10MB limit`)
        return
      }

      setIsUploading(true)
      setUploadError(null)

      try {
        // Upload all files
        await Promise.all(
          acceptedFiles.map(file => uploadMutation.mutateAsync({ file, lotId: lot?.id }))
        )
        toast.success(
          acceptedFiles.length === 1
            ? "PDF uploaded successfully"
            : `${acceptedFiles.length} PDFs uploaded successfully`
        )
      } catch (error) {
        setUploadError("Failed to upload file(s)")
      } finally {
        setIsUploading(false)
      }
    },
    [uploadMutation, lot?.id]
  )

  const onDropRejected = useCallback(() => {
    setUploadError("Only PDF files are allowed")
  }, [])

  const {
    getRootProps,
    getInputProps,
    isDragActive,
    open: openFileDialog,
  } = useDropzone({
    onDrop,
    onDropRejected,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true,
    noKeyboard: true,
    disabled: isLocked,
  })

  // Get attached PDFs from lot record
  const attachedPdfs: string[] = lotWithSpecs?.attached_pdfs || []

  // Internal function to actually perform the submission
  const performSubmission = useCallback(async (overrideUserId?: number) => {
    if (!lot) return
    try {
      await submitForReviewMutation.mutateAsync({ id: lot.id, overrideUserId })

      // Show success dialog instead of toast
      setSubmittedLotRef(lot.reference_number)
      setShowSubmitSuccessDialog(true)
    } catch (error) {
      console.error("Submit for review error:", error)
      toast.error("Failed to submit for review")
    }
  }, [lot, submitForReviewMutation])

  // Handle submit for review (moves from under_review to awaiting_release)
  const handleSubmitForReview = useCallback(async () => {
    console.log("Submit for review clicked", {
      lotId: lot?.id,
      status: currentStatus,
      labInfoLoaded: !!labInfo,
      requirePdf: labInfo?.require_pdf_for_submission,
      attachedPdfsCount: attachedPdfs.length,
    })
    if (!lot) {
      console.error("No lot available")
      return
    }

    // Check if PDF is required and none attached
    // Use explicit check that labInfo is loaded and require_pdf is true
    if (labInfo && labInfo.require_pdf_for_submission && attachedPdfs.length === 0) {
      console.log("Showing override modal - PDF required but none attached")
      // Show override modal
      setShowOverrideModal(true)
      setOverrideUsername("")
      setOverridePassword("")
      setOverrideError(null)
      return
    }

    // No PDF required or PDFs are attached - submit directly
    console.log("Proceeding with submission")
    await performSubmission()
  }, [lot, currentStatus, labInfo, attachedPdfs.length, performSubmission])

  // Handle override verification and submission
  const handleOverrideSubmit = useCallback(async () => {
    if (!overrideUsername || !overridePassword) {
      setOverrideError("Please enter username and password")
      return
    }

    setIsVerifyingOverride(true)
    setOverrideError(null)

    try {
      const result = await authApi.verifyOverride(overrideUsername, overridePassword)

      if (!result.valid) {
        setOverrideError(result.message)
        return
      }

      // Override verified - submit with override user ID
      setShowOverrideModal(false)
      await performSubmission(result.user_id ?? undefined)
    } catch {
      setOverrideError("Failed to verify credentials")
    } finally {
      setIsVerifyingOverride(false)
    }
  }, [overrideUsername, overridePassword, performSubmission])

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

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleCloseAttempt()}>
      <DialogContent
        className="sm:max-w-6xl max-h-[90vh] overflow-hidden flex flex-col"
        showCloseButton={false}
        onKeyDown={(e) => {
          // Handle Escape key with unsaved changes check
          if (e.key === "Escape") {
            e.preventDefault()
            handleCloseAttempt()
          }
        }}
      >

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
        <SimpleBar className="flex-1 min-h-0" style={{ maxHeight: '100%' }}>
          <div className="px-6 py-4">
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
                  originalValuesMap={originalValuesMap}
                  onRequestNextFocus={handleMainTableFocusExit}
                />
              </div>

              {/* Additional Tests accordion */}
              <AdditionalTestsAccordion
                additionalTests={filteredAdditionalTests}
                labTestTypes={labTestTypesData?.items || []}
                onUpdateResult={handleUpdateResult}
                onAddTest={handleAddTest}
                onDeleteResult={handleDeleteResult}
                disabled={isLocked}
                savingRowId={savingRowId}
                triggerRef={additionalTriggerRef}
                onTriggerKeyDown={handleAdditionalTriggerKeyDown}
                addTestButtonRef={addTestButtonRef}
                onAddTestKeyDown={handleAddTestKeyDown}
                onToggle={(open) => setIsAdditionalExpanded(open)}
              />

              {/* Retest History accordion - only shows if lot has retest requests */}
              <div ref={retestsRef}>
                {lot && <RetestsHistoryAccordion lotId={lot.id} />}
              </div>

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
                      onClick={openFileDialog}
                      disabled={isUploading}
                      ref={uploadButtonRef}
                      onKeyDown={handleUploadKeyDown}
                    >
                      <Upload className="h-3.5 w-3.5 mr-1.5" />
                      Upload PDF
                    </Button>
                  )}
                </div>

                {uploadError && (
                  <div className="mb-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-md px-3 py-2">
                    <X className="h-4 w-4" />
                    {uploadError}
                  </div>
                )}

                {/* Visible drop zone */}
                {!isLocked && (
                  <div
                    {...getRootProps()}
                    className={`
                      mb-3 flex flex-col items-center justify-center
                      rounded-lg border-2 border-dashed p-6
                      cursor-pointer transition-colors
                      ${isDragActive
                        ? "border-blue-400 bg-blue-50"
                        : "border-slate-200 bg-slate-50/50 hover:border-slate-300 hover:bg-slate-50"
                      }
                    `}
                  >
                    <input {...getInputProps()} />
                    <Upload className={`h-8 w-8 mb-2 ${isDragActive ? "text-blue-500" : "text-slate-400"}`} />
                    <p className={`text-sm font-medium ${isDragActive ? "text-blue-600" : "text-slate-600"}`}>
                      {isDragActive ? "Drop PDF here" : "Drag and drop PDF here"}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      or click to browse
                    </p>
                  </div>
                )}

                {attachedPdfs.length > 0 && (
                  <div className="flex flex-col gap-2">
                    {attachedPdfs.map((pdf, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => uploadsApi.openPdf(pdf)}
                        className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 hover:bg-slate-100 hover:border-slate-300 transition-colors group text-left"
                      >
                        <FileText className="h-4 w-4 text-slate-400 flex-shrink-0" />
                        <span className="text-sm text-slate-600 truncate flex-1">{pdf}</span>
                        <ExternalLink className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-600 flex-shrink-0" />
                      </button>
                    ))}
                  </div>
                )}

                {isLocked && attachedPdfs.length === 0 && (
                  <p className="text-sm text-slate-400">
                    No PDFs attached.
                  </p>
                )}
              </div>
            </>
          )}
          </div>
        </SimpleBar>

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

        {/* Override modal for submitting without PDF */}
        {showOverrideModal && (
          <div className="mx-6 mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start gap-3 mb-4">
              <ShieldAlert className="h-5 w-5 flex-shrink-0 text-amber-600" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-amber-800">
                  Lab PDF required for submission
                </p>
                <p className="mt-1 text-sm text-amber-700">
                  No lab PDF is attached to this sample. An Admin or QC Manager override is required to continue.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="override-username" className="text-sm font-medium text-slate-700">
                  Username
                </Label>
                <Input
                  id="override-username"
                  type="text"
                  value={overrideUsername}
                  onChange={(e) => setOverrideUsername(e.target.value)}
                  placeholder="Enter admin/QC username"
                  className="h-9"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="override-password" className="text-sm font-medium text-slate-700">
                  Password
                </Label>
                <Input
                  id="override-password"
                  type="password"
                  value={overridePassword}
                  onChange={(e) => setOverridePassword(e.target.value)}
                  placeholder="Enter password"
                  className="h-9"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleOverrideSubmit()
                    }
                  }}
                />
              </div>

              {overrideError && (
                <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded px-3 py-2">
                  <X className="h-4 w-4 flex-shrink-0" />
                  {overrideError}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 mt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowOverrideModal(false)}
                disabled={isVerifyingOverride}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleOverrideSubmit}
                disabled={isVerifyingOverride || !overrideUsername || !overridePassword}
                className="bg-amber-600 hover:bg-amber-700"
              >
                {isVerifyingOverride ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : null}
                Override & Submit
              </Button>
            </div>
          </div>
        )}

        {/* Success Dialog - Nested Dialog for submit approval */}
        <Dialog open={showSubmitSuccessDialog} onOpenChange={setShowSubmitSuccessDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-emerald-600 flex items-center gap-2 text-[18px]">
                <CheckCircle2 className="h-5 w-5" />
                Moved to Final QA Approval
              </DialogTitle>
            </DialogHeader>

            <div className="py-4">
              <p className="text-sm text-slate-600">
                Sample <span className="font-mono font-semibold text-slate-900">{submittedLotRef}</span> has been submitted for final approval.
              </p>
            </div>

            <DialogFooter className="flex-col sm:flex-row gap-2">
              {canGoToRelease && (
                <Button
                  type="button"
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                  onClick={() => {
                    setShowSubmitSuccessDialog(false)
                    onClose()
                    navigate("/release")
                  }}
                >
                  Go to Release Queue
                </Button>
              )}
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowSubmitSuccessDialog(false)
                  if (onSubmitSuccess) {
                    onSubmitSuccess()
                  } else {
                    onClose()
                  }
                }}
              >
                Continue Reviewing
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowSubmitSuccessDialog(false)
                  onClose()
                }}
              >
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Retest Dialog */}
        {lot && (
          <SendForRetestDialog
            isOpen={showRetestDialog}
            onClose={() => setShowRetestDialog(false)}
            lotId={lot.id}
            testResults={testResultRows}
            defaultSpecialInstructions={(() => {
              const sizes = [...new Set(
                (lotWithSpecs?.products ?? [])
                  .map((p) => p.serving_size)
                  .filter(Boolean) as string[]
              )]
              return sizes.length > 0
                ? `Serving Size = ${sizes.sort().join(", ")}`
                : undefined
            })()}
            onSuccess={() => {
              // Refresh lot data to update has_pending_retest flag
              if (lot) {
                queryClient.invalidateQueries({ queryKey: lotKeys.lists() })
                queryClient.invalidateQueries({ queryKey: lotKeys.detailWithSpecs(lot.id) })
              }
            }}
            onComplete={() => {
              // Close both dialogs
              setShowRetestDialog(false)
              onClose()
            }}
          />
        )}

        {/* Footer */}
        <DialogFooter className="flex-shrink-0 border-t border-slate-200 px-6 py-4">
          <div className="flex w-full items-center justify-between">
            {/* Left side - Send for Retest button */}
            <div>
              {canRequestRetest && hasFailingTests && !isLocked && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowRetestDialog(true)}
                  className="text-amber-700 border-amber-300 hover:bg-amber-50 hover:border-amber-400"
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Send for Retest
                </Button>
              )}
            </div>

            {/* Right side - Submit and Save buttons */}
            <div className="flex items-center gap-2">
              {/* Submit for Approval action (available to any authenticated user for under_review status) */}
              {canSubmitForReview && (
                <Button
                  type="button"
                  onClick={handleSubmitForReview}
                  disabled={submitForReviewMutation.isPending}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {submitForReviewMutation.isPending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : null}
                  Submit for Approval
                </Button>
              )}

              {/* Save/Close button */}
            <Button
              type="button"
              ref={saveButtonRef}
              onClick={handleCloseAttempt}
              onKeyDown={handleSaveButtonKeyDown}
            >
                Save & Close
              </Button>
            </div>
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
