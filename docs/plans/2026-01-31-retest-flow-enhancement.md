# Retest Flow Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix retest dialog bugs, add close-both-dialogs behavior, implement expandable retest sub-rows in SampleTable, and block releases for pending retests.

**Architecture:** Frontend-focused changes with a small backend enum addition. The SendForRetestDialog gets a race condition fix and onComplete callback. SampleTable gets expandable rows with lazy-loaded retest data. ReleaseActions blocks release when pending retests exist.

**Tech Stack:** React, TypeScript, TanStack Table, TanStack Query, Tailwind CSS, shadcn/ui, Python/SQLAlchemy (backend enum only)

---

## Task 1: Fix Success Screen Race Condition

**Files:**
- Modify: `frontend/src/components/domain/SendForRetestDialog.tsx:94-108`

**Step 1: Update useEffect to guard against reset when in success state**

Replace lines 94-108:
```tsx
// Auto-select failing tests when dialog opens
// Using useEffect ensures testsWithResults is populated before we filter
useEffect(() => {
  if (isOpen && testsWithResults.length > 0 && dialogState !== "success") {
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
  }
}, [isOpen, testsWithResults, dialogState])
```

**Step 2: Verify the change compiles**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build 2>&1 | head -50`
Expected: No TypeScript errors

**Step 3: Commit**

```bash
git add frontend/src/components/domain/SendForRetestDialog.tsx
git commit -m "$(cat <<'EOF'
fix: prevent success screen reset in SendForRetestDialog

Guard useEffect from resetting dialogState when already in "success"
state. This prevents the success screen from disappearing when
query invalidation triggers testsWithResults to update.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add onComplete Prop to SendForRetestDialog

**Files:**
- Modify: `frontend/src/components/domain/SendForRetestDialog.tsx:44-55, 59-65, 362`

**Step 1: Add onComplete to props interface**

At line 54, add new prop after onSuccess:
```tsx
interface SendForRetestDialogProps {
  /** Whether the dialog is open */
  isOpen: boolean
  /** Callback when the dialog should close */
  onClose: () => void
  /** The lot ID to create retest request for */
  lotId: number
  /** All test result rows for the lot */
  testResults: TestResultRow[]
  /** Callback when retest request is successfully created */
  onSuccess?: () => void
  /** Callback when user clicks Done on success screen (closes both dialogs) */
  onComplete?: () => void
}
```

**Step 2: Destructure onComplete in component**

Update the destructuring (around line 59-65):
```tsx
export function SendForRetestDialog({
  isOpen,
  onClose,
  lotId,
  testResults,
  onSuccess,
  onComplete,
}: SendForRetestDialogProps) {
```

**Step 3: Update Done button to call onComplete**

Replace line 362:
```tsx
<Button onClick={() => {
  if (onComplete) {
    onComplete()
  } else {
    onClose()
  }
}}>Done</Button>
```

**Step 4: Verify the change compiles**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build 2>&1 | head -50`
Expected: No TypeScript errors

**Step 5: Commit**

```bash
git add frontend/src/components/domain/SendForRetestDialog.tsx
git commit -m "$(cat <<'EOF'
feat: add onComplete prop to SendForRetestDialog

Allows parent component to handle both dialogs closing when user
clicks Done on the success screen.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Wire onComplete in SampleModal

**Files:**
- Modify: `frontend/src/components/domain/SampleModal/index.tsx:1058-1073`

**Step 1: Add onComplete handler to SendForRetestDialog**

Replace lines 1058-1073:
```tsx
{/* Retest Dialog */}
{lot && (
  <SendForRetestDialog
    isOpen={showRetestDialog}
    onClose={() => setShowRetestDialog(false)}
    lotId={lot.id}
    testResults={testResultRows}
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
```

**Step 2: Verify the change compiles**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build 2>&1 | head -50`
Expected: No TypeScript errors

**Step 3: Commit**

```bash
git add frontend/src/components/domain/SampleModal/index.tsx
git commit -m "$(cat <<'EOF'
feat: close both dialogs when Done clicked on retest success

Wire onComplete prop to close both the retest dialog and the
sample modal when user clicks Done on the success screen.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add RetestSubRows Component

**Files:**
- Create: `frontend/src/components/domain/RetestSubRows.tsx`

**Step 1: Create the RetestSubRows component**

```tsx
/**
 * Retest Sub-Rows Component
 *
 * Renders expandable sub-rows for lots with retest requests.
 * Each retest request gets its own row showing reference, tests, and status.
 */

import { Loader2, RefreshCw, CheckCircle2, Clock, AlertTriangle } from "lucide-react"
import { useRetestRequests } from "@/hooks/useRetests"
import { TableCell, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import type { RetestRequest, RetestStatus } from "@/types"

interface RetestSubRowsProps {
  /** Lot ID to fetch retests for */
  lotId: number
  /** Number of columns in the parent table (for colspan) */
  colSpan: number
  /** Callback when a retest row is clicked */
  onRetestClick: (retestId: number) => void
}

export function RetestSubRows({ lotId, colSpan, onRetestClick }: RetestSubRowsProps) {
  const { data: retestData, isLoading } = useRetestRequests(lotId)
  const retestRequests = retestData?.items ?? []

  if (isLoading) {
    return (
      <TableRow className="bg-amber-50/30">
        <TableCell colSpan={colSpan} className="py-3">
          <div className="flex items-center gap-2 text-sm text-amber-600 pl-8">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading retests...
          </div>
        </TableCell>
      </TableRow>
    )
  }

  if (retestRequests.length === 0) {
    return null
  }

  return (
    <>
      {retestRequests.map((request) => (
        <RetestRow
          key={request.id}
          request={request}
          colSpan={colSpan}
          onClick={() => onRetestClick(request.id)}
        />
      ))}
    </>
  )
}

interface RetestRowProps {
  request: RetestRequest
  colSpan: number
  onClick: () => void
}

function RetestRow({ request, colSpan, onClick }: RetestRowProps) {
  const testNames = request.items
    .map((item) => item.test_type)
    .filter(Boolean)
    .join(", ") || "—"

  const isPending = request.status === "pending"
  const isReviewRequired = request.status === "review_required"

  return (
    <TableRow
      onClick={onClick}
      className={cn(
        "cursor-pointer transition-colors",
        isPending && "bg-amber-50/50 hover:bg-amber-100/50",
        isReviewRequired && "bg-yellow-50/50 hover:bg-yellow-100/50",
        !isPending && !isReviewRequired && "bg-slate-50/50 hover:bg-slate-100/50"
      )}
    >
      <TableCell colSpan={colSpan} className="py-2">
        <div className="flex items-center gap-4 pl-8">
          {/* Indent indicator */}
          <div className="flex items-center gap-2 min-w-[140px]">
            <RefreshCw className="h-3.5 w-3.5 text-amber-500" />
            <span className="font-mono text-sm font-medium text-amber-800">
              {request.reference_number}
            </span>
          </div>

          {/* Test names */}
          <div className="flex-1 text-sm text-slate-600 truncate" title={testNames}>
            {testNames}
          </div>

          {/* Status badge */}
          <StatusBadge status={request.status} />
        </div>
      </TableCell>
    </TableRow>
  )
}

function StatusBadge({ status }: { status: RetestStatus }) {
  if (status === "completed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
        <CheckCircle2 className="h-3 w-3" />
        Completed
      </span>
    )
  }

  if (status === "review_required") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700">
        <AlertTriangle className="h-3 w-3" />
        Review Required
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
      <Clock className="h-3 w-3" />
      Pending
    </span>
  )
}

export default RetestSubRows
```

**Step 2: Verify the change compiles**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build 2>&1 | head -50`
Expected: No TypeScript errors (may warn about unused - that's fine, we'll use it next)

**Step 3: Commit**

```bash
git add frontend/src/components/domain/RetestSubRows.tsx
git commit -m "$(cat <<'EOF'
feat: add RetestSubRows component for expandable retest rows

Creates a new component that renders sub-rows for each retest request
associated with a lot. Supports pending, completed, and review_required
statuses. Uses lazy loading via useRetestRequests hook.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Add review_required to RetestStatus Type

**Files:**
- Modify: `frontend/src/types/index.ts:301`

**Step 1: Update RetestStatus type**

Replace line 301:
```tsx
export type RetestStatus = 'pending' | 'completed' | 'review_required'
```

**Step 2: Verify the change compiles**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build 2>&1 | head -50`
Expected: No TypeScript errors

**Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "$(cat <<'EOF'
feat: add review_required to RetestStatus type

Supports the new status for when retest value matches original value
and requires QC review before completion.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add Expandable Rows to SampleTable

**Files:**
- Modify: `frontend/src/components/domain/SampleTable.tsx`

**Step 1: Add imports and state for expansion**

Add to imports at top of file (around line 13):
```tsx
import { ArrowUpDown, ArrowUp, ArrowDown, FileText, Search, ChevronLeft, ChevronRight, ChevronRight as ChevronRightIcon, ChevronDown } from "lucide-react"
import { RetestSubRows } from "./RetestSubRows"
```

Add state after line 97 (after statusFilter state):
```tsx
const [expandedLotIds, setExpandedLotIds] = useState<Set<number>>(new Set())
```

**Step 2: Add expand toggle function**

Add after state declarations:
```tsx
const toggleExpand = useCallback((lotId: number, e: React.MouseEvent) => {
  e.stopPropagation()
  setExpandedLotIds((prev) => {
    const next = new Set(prev)
    if (next.has(lotId)) {
      next.delete(lotId)
    } else {
      next.add(lotId)
    }
    return next
  })
}, [])
```

**Step 3: Add expand column to columns array**

Add as first column in the columns useMemo (before reference_number column around line 101):
```tsx
columnHelper.display({
  id: "expand",
  header: () => null,
  cell: ({ row }) => {
    const lot = row.original
    const hasRetests = lot.has_pending_retest
    const isExpanded = expandedLotIds.has(lot.id)

    if (!hasRetests) {
      return <div className="w-6" /> // Empty space for alignment
    }

    return (
      <button
        type="button"
        onClick={(e) => toggleExpand(lot.id, e)}
        className="p-1 rounded hover:bg-slate-100 transition-colors"
        aria-label={isExpanded ? "Collapse retests" : "Expand retests"}
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-amber-600" />
        ) : (
          <ChevronRightIcon className="h-4 w-4 text-amber-600" />
        )}
      </button>
    )
  },
  size: 40,
}),
```

**Step 4: Add retest badge to status column**

Update the status column cell (around line 177-185) to include a retest badge:
```tsx
columnHelper.accessor("status", {
  header: ({ column }) => (
    <SortableHeader column={column} label="Status" />
  ),
  cell: (info) => {
    const status = info.getValue()
    const config = STATUS_CONFIG[status]
    const lot = info.row.original
    return (
      <div className="flex items-center gap-2">
        <Badge variant={getStatusColor(status)}>
          {config.label}
        </Badge>
        {lot.has_pending_retest && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
            <RefreshCw className="h-3 w-3" />
          </span>
        )}
      </div>
    )
  },
  filterFn: (row, columnId, filterValue) => {
    if (filterValue === "all") return true
    return row.getValue(columnId) === filterValue
  },
}),
```

Add RefreshCw to imports.

**Step 5: Update table body to render sub-rows**

Replace the table body rows rendering (around line 356-375):
```tsx
{table.getRowModel().rows.length === 0 ? (
  <TableRow>
    <TableCell
      colSpan={columns.length}
      className="h-24 text-center text-slate-500"
    >
      No samples found
    </TableCell>
  </TableRow>
) : (
  table.getRowModel().rows.map((row) => (
    <>
      <TableRow
        key={row.id}
        onClick={() => onRowClick(row.original)}
        className={cn(
          "cursor-pointer transition-colors",
          getRowClassName(row.original)
        )}
      >
        {row.getVisibleCells().map((cell) => (
          <TableCell key={cell.id} className="text-[14px]">
            {flexRender(
              cell.column.columnDef.cell,
              cell.getContext()
            )}
          </TableCell>
        ))}
      </TableRow>
      {expandedLotIds.has(row.original.id) && (
        <RetestSubRows
          lotId={row.original.id}
          colSpan={columns.length}
          onRetestClick={(retestId) => {
            // For now, just open the lot - later we can scroll to retest section
            onRowClick(row.original)
          }}
        />
      )}
    </>
  ))
)}
```

**Step 6: Add Fragment import if needed**

Ensure React Fragment is available by using `<>` syntax or import { Fragment }.

**Step 7: Verify the change compiles**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build 2>&1 | head -50`
Expected: No TypeScript errors

**Step 8: Commit**

```bash
git add frontend/src/components/domain/SampleTable.tsx
git commit -m "$(cat <<'EOF'
feat: add expandable retest sub-rows to SampleTable

- Add chevron column for lots with pending retests
- Show retest badge on status column when has_pending_retest is true
- Expand/collapse to show RetestSubRows for each retest request
- Lazy load retest data only when row is expanded

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Block Release for Pending Retests

**Files:**
- Modify: `frontend/src/components/domain/ReleaseActions.tsx:299-313`

**Step 1: Add Tooltip imports if not present**

Check imports at top of file and add if needed:
```tsx
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
```

**Step 2: Add hasPendingRetest check**

Add after line 69 (after retestRequests declaration):
```tsx
const hasPendingRetest = retestRequests.some(r => r.status === "pending")
```

**Step 3: Update Approve & Release button with blocking logic**

Replace lines 299-313:
```tsx
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
```

**Step 4: Verify the change compiles**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build 2>&1 | head -50`
Expected: No TypeScript errors

**Step 5: Commit**

```bash
git add frontend/src/components/domain/ReleaseActions.tsx
git commit -m "$(cat <<'EOF'
feat: block release when pending retest exists

Disable the Approve & Release button and show a tooltip explaining
that release is blocked while a retest is pending.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Auto-Expand Retests History Accordion When Pending

**Files:**
- Modify: `frontend/src/components/domain/SampleModal/RetestsHistoryAccordion.tsx:21-31`

**Step 1: Update props interface**

Replace interface at lines 21-24:
```tsx
interface RetestsHistoryAccordionProps {
  /** Lot ID to fetch retest requests for */
  lotId: number
  /** Whether to auto-expand when pending retests exist */
  autoExpandWhenPending?: boolean
}
```

**Step 2: Update component to accept prop and auto-expand**

Replace lines 30-37:
```tsx
export function RetestsHistoryAccordion({
  lotId,
  autoExpandWhenPending = true
}: RetestsHistoryAccordionProps) {
  // Fetch retest requests for this lot
  const { data: retestData, isLoading } = useRetestRequests(lotId)
  const downloadPdfMutation = useDownloadRetestPdf()

  const retestRequests = retestData?.items ?? []
  const hasPendingRetests = retestRequests.some(r => r.status === "pending" || r.status === "review_required")

  const [isExpanded, setIsExpanded] = useState(false)

  // Auto-expand when pending retests and autoExpandWhenPending is true
  useEffect(() => {
    if (autoExpandWhenPending && hasPendingRetests && !isLoading) {
      setIsExpanded(true)
    }
  }, [autoExpandWhenPending, hasPendingRetests, isLoading])
```

**Step 3: Add useEffect import**

Add to imports at top:
```tsx
import { useState, useEffect } from "react"
```

**Step 4: Verify the change compiles**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build 2>&1 | head -50`
Expected: No TypeScript errors

**Step 5: Commit**

```bash
git add frontend/src/components/domain/SampleModal/RetestsHistoryAccordion.tsx
git commit -m "$(cat <<'EOF'
feat: auto-expand retests accordion when pending retests exist

Add autoExpandWhenPending prop (default true) that automatically
expands the accordion when there are pending or review_required retests.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Add REVIEW_REQUIRED Status to Backend Enum

**Files:**
- Modify: `backend/app/models/enums.py:71-75`

**Step 1: Update RetestStatus enum**

Replace lines 71-75:
```python
class RetestStatus(str, enum.Enum):
    """Retest request status enumeration."""

    PENDING = "pending"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
```

**Step 2: Verify no Python syntax errors**

Run: `cd /Users/gregsimek/Code/COA-creator/backend && python -c "from app.models.enums import RetestStatus; print(list(RetestStatus))"`
Expected: `[<RetestStatus.PENDING: 'pending'>, <RetestStatus.REVIEW_REQUIRED: 'review_required'>, <RetestStatus.COMPLETED: 'completed'>]`

**Step 3: Commit**

```bash
git add backend/app/models/enums.py
git commit -m "$(cat <<'EOF'
feat: add REVIEW_REQUIRED status to RetestStatus enum

New intermediate status for when retest result matches original value
and requires QC review before being marked as completed.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Update check_and_complete_retest for Same-Value Detection

**Files:**
- Modify: `backend/app/services/retest_service.py:274-344`

**Step 1: Update check_and_complete_retest method**

Replace lines 274-344:
```python
def check_and_complete_retest(
    self, db: Session, test_result_id: int
) -> Optional[RetestRequest]:
    """
    Check if updating a test result completes any pending retests.

    This should be called after a test result value is updated.
    If new value matches original value, sets status to REVIEW_REQUIRED.
    If new value differs from original, auto-completes the retest.

    Args:
        db: Database session
        test_result_id: ID of the test result that was updated

    Returns:
        The completed/review_required RetestRequest if one was updated, None otherwise
    """
    # Find pending retest items for this test result
    items = (
        db.query(RetestItem)
        .join(RetestRequest)
        .filter(
            RetestItem.test_result_id == test_result_id,
            RetestRequest.status == RetestStatus.PENDING,
        )
        .all()
    )

    updated_request = None

    for item in items:
        retest_request = item.retest_request

        # Check status of ALL items in this request
        all_updated = True
        any_same_as_original = False

        for req_item in retest_request.items:
            test_result = (
                db.query(TestResult)
                .filter(TestResult.id == req_item.test_result_id)
                .first()
            )
            if test_result:
                if test_result.result_value == req_item.original_value:
                    # Value unchanged from original - either not updated or same value
                    # Check if this is the item we just updated
                    if req_item.test_result_id == test_result_id:
                        # User entered same value as original - needs review
                        any_same_as_original = True
                    else:
                        # Other items still need updating
                        all_updated = False
                        break

        if all_updated:
            if any_same_as_original:
                # At least one value matches original - needs QC review
                retest_request.status = RetestStatus.REVIEW_REQUIRED
                logger.info(
                    f"Retest {retest_request.reference_number} requires review "
                    f"(new value matches original)"
                )
            else:
                # All values differ from original - auto-complete
                retest_request.status = RetestStatus.COMPLETED
                retest_request.completed_at = datetime.utcnow()
                logger.info(
                    f"Retest {retest_request.reference_number} auto-completed"
                )

            updated_request = retest_request

            # Check if lot has any OTHER pending retests
            pending_count = (
                db.query(RetestRequest)
                .filter(
                    RetestRequest.lot_id == retest_request.lot_id,
                    RetestRequest.status == RetestStatus.PENDING,
                    RetestRequest.id != retest_request.id,
                )
                .count()
            )

            # Also check for review_required retests - lot should still show pending
            review_required_count = (
                db.query(RetestRequest)
                .filter(
                    RetestRequest.lot_id == retest_request.lot_id,
                    RetestRequest.status == RetestStatus.REVIEW_REQUIRED,
                )
                .count()
            )

            if pending_count == 0 and review_required_count == 0:
                retest_request.lot.has_pending_retest = False
            elif retest_request.status == RetestStatus.REVIEW_REQUIRED:
                # Keep flag true if review required
                retest_request.lot.has_pending_retest = True

    if updated_request:
        db.commit()

    return updated_request
```

**Step 2: Verify no Python syntax errors**

Run: `cd /Users/gregsimek/Code/COA-creator/backend && python -c "from app.services.retest_service import retest_service; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/services/retest_service.py
git commit -m "$(cat <<'EOF'
feat: detect same-value retests and require review

Update check_and_complete_retest to set status to REVIEW_REQUIRED
when the new test result value matches the original value. This
prevents auto-completion and requires QC to manually review.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Update RetestsHistoryAccordion to Show Review Required Badge

**Files:**
- Modify: `frontend/src/components/domain/SampleModal/RetestsHistoryAccordion.tsx:61-76`

**Step 1: Import AlertTriangle icon**

Add to imports:
```tsx
import { ChevronDown, RefreshCw, CheckCircle2, Clock, Download, AlertTriangle } from "lucide-react"
```

**Step 2: Update getStatusBadge function**

Replace lines 61-76:
```tsx
const getStatusBadge = (request: RetestRequest) => {
  if (request.status === "completed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
        <CheckCircle2 className="h-3 w-3" />
        Completed
      </span>
    )
  }
  if (request.status === "review_required") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700">
        <AlertTriangle className="h-3 w-3" />
        Review Required
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
      <Clock className="h-3 w-3" />
      Pending
    </span>
  )
}
```

**Step 3: Verify the change compiles**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build 2>&1 | head -50`
Expected: No TypeScript errors

**Step 4: Commit**

```bash
git add frontend/src/components/domain/SampleModal/RetestsHistoryAccordion.tsx
git commit -m "$(cat <<'EOF'
feat: add Review Required badge to retests history

Display a yellow "Review Required" badge for retests that matched
the original value and need QC review.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Final Build Verification

**Step 1: Run full frontend build**

Run: `cd /Users/gregsimek/Code/COA-creator/frontend && npm run build`
Expected: Build completes successfully

**Step 2: Run backend tests**

Run: `cd /Users/gregsimek/Code/COA-creator/backend && python -m pytest tests/test_retest_service.py -v 2>&1 | tail -20`
Expected: Tests pass (or skip if not present)

**Step 3: Run full test suite (optional)**

Run: `cd /Users/gregsimek/Code/COA-creator/backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: Tests pass

---

## Verification Checklist

After completing all tasks, manually verify:

1. **Bug fix**: Create retest → success screen stays visible until "Done" clicked
2. **Close both**: Click "Done" → Retest dialog AND Sample Modal both close
3. **SampleTable expand**:
   - Lot with retests shows chevron + badge
   - Click chevron → expands to show sub-rows
   - Each retest is separate sub-row with reference, tests, status
   - Click sub-row → opens Sample Modal
4. **Release blocking**: Release button disabled with tooltip when pending retest
5. **Auto-expand accordion**: Open Sample Modal with pending retest → Retests History expanded
6. **Completion logic**: Enter same value as original → shows "Review Required" badge
