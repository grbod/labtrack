# Plan: 6 Bug Fixes for LabTrack

## Context

After implementing the spec preview panel and re-seeding the production DB, several bugs were discovered during end-to-end testing of the full sample-to-release workflow. These range from input validation issues to missing features and broken Release page functionality.

---

## Bug 1: Y&M "<100" — Add `<`/`>` Prefix Toggle to Numeric Inputs

**Problem:** Labs report results like "<100" but `SmartResultInput` renders `<input type="number">` for specs starting with `<`/`>`, rejecting the text prefix. Backend stores `result_value` as TEXT (model line 46), so it can handle "<100" just fine.

**Root cause:** `getInputTypeForSpec()` (`spec-validation.ts:168`) returns `'number'` for specs starting with `<`/`>` → HTML number input rejects text.

### Changes

**`frontend/src/components/domain/SampleModal/SmartResultInput.tsx`** (line 340-353, the `case 'number':` block)

Replace the plain `<Input type="number">` with a composite input:

```tsx
case 'number': {
  // Parse existing prefix from value (e.g., "<100" → prefix="<", num="100")
  const prefixMatch = localValue.match(/^([<>])\s*(.*)$/)
  const currentPrefix = prefixMatch ? prefixMatch[1] : ""
  const numericPart = prefixMatch ? prefixMatch[2] : localValue

  return (
    <div className="flex items-center gap-0.5">
      <button
        type="button"
        tabIndex={-1}
        className={cn(
          "h-8 w-7 shrink-0 rounded-l-md border border-r-0 text-xs font-mono",
          "hover:bg-slate-100 transition-colors",
          currentPrefix ? "bg-blue-50 text-blue-700 border-blue-500" : "bg-slate-50 text-slate-400 border-slate-200"
        )}
        onMouseDown={(e) => e.preventDefault()} // prevent blur
        onClick={() => {
          const next = currentPrefix === "<" ? ">" : currentPrefix === ">" ? "" : "<"
          const newVal = next ? `${next}${numericPart}` : numericPart
          setLocalValue(newVal)
          onChange(newVal)
        }}
      >
        {currentPrefix || "="}
      </button>
      <Input
        ref={inputRef}
        type="number"
        step="any"
        value={numericPart}
        onChange={(e) => {
          const newVal = currentPrefix ? `${currentPrefix}${e.target.value}` : e.target.value
          setLocalValue(newVal)
        }}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        className={cn("h-8 text-sm border-blue-500 focus-visible:ring-blue-500 rounded-l-none", className)}
        placeholder="0"
      />
    </div>
  )
}
```

**State initialization** (line 53): Update `localValue` sync — when `value` starts with `<`/`>`, parse it properly.

**`frontend/src/lib/spec-validation.ts`** — No changes needed. `evaluateResult()` (lines 103-112) already handles `<` prefix in pass/fail evaluation. `getInputTypeForSpec()` still returns `'number'` which is correct.

---

## Bug 2: Spec Preview Toast Missing in Multi-SKU

**Problem:** SpecPreviewPanel slide-in works for standard and parent lot product selection but not for multi-SKU composite.

**Root cause:** Code at `CreateSample.tsx:605` DOES call `showSpecPreview(product)`. The `showSpecPreview` callback (line 147-151) checks `labInfo?.show_spec_preview_on_sample`. Need runtime debugging.

### Investigation steps during implementation

1. Add `console.log` in the multi-SKU `onSelect` callback (line 598) to verify it fires
2. Add `console.log` in `showSpecPreview` to verify `labInfo?.show_spec_preview_on_sample` is true
3. Add `console.log` in `SpecPreviewPanel` useEffect (line 37) to verify `product` prop arrives
4. Check if `setCompositeProducts` (line 599) causes a cascade that resets `specPreviewProduct`

### Likely fix

**`frontend/src/pages/CreateSample.tsx`** (line 598-606)

If the issue is React batching causing `setCompositeProducts` to override the panel state: defer the preview call with `setTimeout`:

```tsx
onSelect={(product) => {
  setCompositeProducts(prev =>
    prev.map(cp => cp.id === rowId
      ? { ...cp, product_id: product.id, product_name: product.display_name }
      : cp
    )
  )
  // Defer to avoid state batching conflicts with setCompositeProducts
  setTimeout(() => showSpecPreview(product), 0)
}}
```

---

## Bug 3: Add "Odor" to Organoleptic Specs

**Problem:** "Odor" is missing from seed data. Only "Appearance" (seed_tests.csv:135) and "Taste" (seed_tests.csv:136) exist as organoleptic/physical specs.

### Changes

**`backend/seed_tests.csv`** — Insert after line 136 (Taste):
```csv
"Odor","Organoleptic","Physical","","Conforms to standard"
```

**`backend/product_test_mapping.csv`** (204 product rows) — For every row:
- Append `; Odor` to the "Required Tests" column
- Append `; Conforms to standard` to the "Specifications" column
- Increment "Test Count" by 1 (from 6 to 7)

Example: line 2 changes from:
```
Athletes Best,Energy Protein,Vanilla,...,6,Escherichia coli; Salmonella spp.; Total Plate Count; Yeast & Mold; Appearance; Taste,"Negative; Negative; < 10,000 CFU/g; < 1,000 CFU/g; Fine off-white to cream powder; Characteristic Vanilla"
```
to:
```
Athletes Best,Energy Protein,Vanilla,...,7,Escherichia coli; Salmonella spp.; Total Plate Count; Yeast & Mold; Appearance; Taste; Odor,"Negative; Negative; < 10,000 CFU/g; < 1,000 CFU/g; Fine off-white to cream powder; Characteristic Vanilla; Conforms to standard"
```

**`backend/scripts/seed_odor_specs.py`** (new script) — Standalone idempotent script for existing DBs:
1. Check if "Odor" lab test type exists → create with `test_method="Organoleptic"`, `test_category="Physical"`, `default_specification="Conforms to standard"` if not
2. For each Product, check if ProductTestSpecification exists for Odor → create with `specification="Conforms to standard"`, `is_required=True` if not
3. Log summary: X new specs created, Y already existed

Pattern: follow existing `backend/scripts/seed_product_test_specs.py`.

---

## Bug 4 (Deferred): Inline Spec Override — NOT in this round

---

## Bug 5: Source Documents 404 on Release Page

**Problem:** SourcePDFViewer shows "Failed to load documents — Request failed with status code 404" for lot 260223-001 even though PDFs were uploaded.

**Root cause investigation:** The serve endpoint (`release.py:1009`) looks for files at `Path(settings.upload_path) / "pdfs" / filename`. Multiple 404 points: (1) filename in DB doesn't match disk, (2) wrong upload_path, (3) file physically missing.

### Changes

**Investigation during implementation:**
1. SSH to VPS: `ls /opt/labtrack/backend/uploads/pdfs/` — check what files exist
2. Query DB: `SELECT attached_pdfs FROM lots WHERE lot_number LIKE '260223%'`
3. Compare filenames

**`frontend/src/components/domain/SourcePDFViewer.tsx`** (lines 190-209)

Change the sequential fetch loop to `Promise.allSettled` for graceful per-file error handling:

```tsx
const fetchAllPdfs = async () => {
  setLoading(true)
  setError(null)

  const promises = sourcePdfs.map(async (filename) => {
    const blob = await releaseApi.getSourcePdfBlob(lotId, productId, filename)
    const url = URL.createObjectURL(blob)
    return { filename, url, numPages: 0 } as PdfData
  })

  const settled = await Promise.allSettled(promises)
  const succeeded: PdfData[] = []
  const failed: string[] = []

  for (let i = 0; i < settled.length; i++) {
    if (settled[i].status === 'fulfilled') {
      succeeded.push((settled[i] as PromiseFulfilledResult<PdfData>).value)
    } else {
      failed.push(sourcePdfs[i])
    }
  }

  setPdfDataList(succeeded)
  if (failed.length > 0 && succeeded.length === 0) {
    setError(`Failed to load ${failed.length} document(s)`)
  } else if (failed.length > 0) {
    // Partial success - show warning but still display loaded PDFs
    setPartialError(`${failed.length} of ${sourcePdfs.length} documents failed to load`)
  }

  setLoading(false)
}
```

Add `partialError` state for showing a warning banner above successfully loaded PDFs.

**`backend/app/api/v1/endpoints/release.py`** (line 1013) — Improve 404 error detail:
```python
detail=f"Source PDF file '{filename}' not found at expected path"
```

---

## Bug 6: Approve Button Not Working on Release Page

**Problem:** Clicking "Approve & Release" → "Approve" in the confirmation dialog does nothing visible.

**Root cause:** The approve endpoint (`release.py:391-518`) checks: (1) `signature_path` on user (line 416), (2) `full_name` (line 422), (3) `title` (line 428), (4) lot status == AWAITING_RELEASE (line 442). Any failure returns 400 which is caught and shown as a toast (`ReleaseActions.tsx:133-140`). The toast may not be noticeable.

### Changes

**Investigation during implementation:**
1. SSH to VPS: check admin user's `signature_path` — `SELECT signature_path, full_name, title FROM users WHERE username='admin'`
2. Check lot status: `SELECT status FROM lots WHERE lot_number LIKE '260223%'`
3. Reproduce in browser and check network tab for the actual 400 response

**`frontend/src/components/domain/ReleaseActions.tsx`** (lines 128-141)

Replace silent toast with an inline error banner that persists until dismissed:

```tsx
const [approveError, setApproveError] = useState<string | null>(null)

const handleApproveConfirm = async () => {
  setApproveError(null)
  try {
    await onApprove(customerId ?? undefined, notes || undefined)
    setShowApproveConfirm(false)
    setShowSuccessDialog(true)
  } catch (error: unknown) {
    console.error("Failed to approve release:", error)
    setShowApproveConfirm(false)
    const message = extractApiErrorMessage(error, "Failed to approve release", {
      403: "You don't have permission to approve releases. QC Manager or Admin role required.",
      400: "Cannot approve release. Check the error details below.",
    })
    // Show inline error instead of just toast
    setApproveError(message)
    toast.error(message, { duration: 5000 })
  }
}
```

Then render an error banner above the "Approve & Release" button (line 360):

```tsx
{approveError && (
  <div className="p-3 rounded-md bg-red-50 border border-red-200">
    <p className="text-sm text-red-800 font-medium">Release Failed</p>
    <p className="text-xs text-red-600 mt-1">{approveError}</p>
    {approveError.includes("signature") && (
      <Button variant="link" size="sm" className="text-xs h-auto p-0 mt-1"
        onClick={() => window.open('/settings', '_blank')}>
        Upload signature in Settings →
      </Button>
    )}
  </div>
)}
```

---

## Bug 7: COA Preview Placeholder Data — Skip

User will update company info via Settings manually. No code changes this round.

---

## Implementation Order

1. **Bug 3** (Odor specs) — seed data + script, independent
2. **Bug 1** (prefix toggle) — self-contained SmartResultInput change
3. **Bug 2** (multi-SKU toast) — debug and fix in CreateSample
4. **Bug 5** (source docs 404) — VPS investigation + graceful error handling
5. **Bug 6** (approve button) — VPS investigation + inline error banner

## Files Summary

| File | Bug | Change |
|------|-----|--------|
| `backend/seed_tests.csv` | 3 | Add Odor row |
| `backend/product_test_mapping.csv` | 3 | Append Odor to all 204 products |
| `backend/scripts/seed_odor_specs.py` | 3 | New idempotent script |
| `frontend/src/components/domain/SampleModal/SmartResultInput.tsx` | 1 | Add prefix toggle for `case 'number'` |
| `frontend/src/pages/CreateSample.tsx` | 2 | Fix multi-SKU spec preview |
| `frontend/src/components/domain/SourcePDFViewer.tsx` | 5 | `Promise.allSettled` + partial error |
| `backend/app/api/v1/endpoints/release.py` | 5 | Better 404 message |
| `frontend/src/components/domain/ReleaseActions.tsx` | 6 | Inline error banner |

## Verification

1. `cd frontend && npm run build` — no build errors
2. `cd backend && .venv/bin/python -m pytest tests/ -v` — existing tests pass
3. **Bug 1:** Create sample → enter result for a `< 100` spec → click prefix toggle to `<`, type `100` → value stored as `<100` → pass/fail evaluates correctly
4. **Bug 2:** Create multi-SKU sample → select product in composite table → spec preview toast slides in from bottom-right
5. **Bug 3:** Run `seed_odor_specs.py` on VPS → verify Odor test type exists and all products have Odor spec
6. **Bug 5:** On Release page, source docs degrade gracefully (partial load shows warning, full failure shows error)
7. **Bug 6:** On Release page, approve failure shows persistent inline error with actionable guidance (e.g., "upload signature" link)
