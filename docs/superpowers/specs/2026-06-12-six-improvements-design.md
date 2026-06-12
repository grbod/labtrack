# Six Improvements: Ad-hoc Tests, COC Archive, Release Queue Actions, UX Polish, Kanagawa Dragon Dark Mode

**Date:** 2026-06-12
**Status:** Approved by Greg (interview + grill session)

Delivery order: 1 → 2 → 3 → 4 → 5 → 6 below.

---

## 1. Fix Ad-hoc "Additional Tests" in the Sample Modal

### Problem
The Additional Tests input in the sample detail modal is a dead text field: no autocomplete dropdown appears, and typed text doesn't link to any defined test. Root causes found in code:
- `AdditionalTestsAccordion` expects test-type data for its filter but the dropdown never renders results.
- `SampleModal.handleAddTest` drops the selected `labTestTypeId` and posts only a free-text `test_type`, so even a successful add wouldn't link to the Lab Test Type.

### Requirements
- Typing in the field filters the defined Lab Test Types (name + category, case-insensitive) into a dropdown; selection is **only** from defined tests, free text cannot be submitted.
- Selecting a test creates a TestResult linked to the `lab_test_type_id`, auto-filling spec, unit, and method from the Lab Test Type definition. All three remain editable for this lot.
- **Binding but removable:** an added ad-hoc test counts like a required test (blocks completion until a result is entered; a failing result sends the lot to Needs Attention), but it can be deleted while it has no result.
- **Include-on-COA toggle:** each ad-hoc test row has an "Include on COA" checkbox, **default ON**. When off, the test stays internal and never prints on the certificate.
- On the generated COA, included ad-hoc tests slot into their proper category section per the admin-defined category order (alphabetical within section). No new ordering UI; linking the test type ID provides the category.

### Touchpoints
- Frontend: `SampleModal/index.tsx` (`handleAddTest`), `AdditionalTestsAccordion.tsx`.
- Backend: TestResult create endpoint/schema accepts `lab_test_type_id` and `include_on_coa`; COA generation filters on `include_on_coa` and uses the linked category for ordering.
- Migration: `include_on_coa` boolean on TestResult (default true).

---

## 2. Chain of Custody: Archive Original + Re-download

### Problem
The COC PDF is generated on the fly at sample creation; if the printout/PDF is lost there is no way to get it again.

### Requirements
- At first generation, persist the COC PDF through the existing storage layer (local filesystem or R2) and save the storage key on the lot.
- **The archive is immutable.** Re-download always serves the original byte-for-byte; it is the record of what was sent to the lab. No regenerate action, no silent refresh on lot edits.
- A "Download Chain of Custody" button in the sample detail modal (opened from the Sample Tracker) serves the archived PDF.
- Lots created before this feature (no archived PDF): one-time generate-and-archive fallback on first download, so the button works for every lot.

### Touchpoints
- Backend: COC generation endpoint stores PDF + key on Lot; new/extended download endpoint serving the archive.
- Frontend: button in `SampleModal` header/footer; API + hook additions.
- Migration: `coc_storage_key` (nullable string) on Lot.

---

## 3. Release Queue: Reject + Return for Review

### Problem
The Release Queue has no way to reject a lot or send it back for correction.

### Requirements
Two actions on awaiting-release lots, **Admin + QC Manager only**:

**Reject**
- Requires a reason (mandatory text).
- Lot moves to `REJECTED` (existing recoverable status; existing resubmission path applies).
- Audit-trail entry with actor + reason.

**Return for Review**
- Requires a reason (mandatory text).
- New allowed transition: `AWAITING_RELEASE → NEEDS_ATTENTION`, with the return reason stored on the lot.
- In the Sample Tracker the card renders with an **amber tint**, a **"Returned" chip**, and the return reason text. The amber treatment persists until the lot re-enters the release queue.
- **Clearing a return requires both:** (a) the underlying issue fixed, and (b) a **response note** explaining what happened and why (e.g. data entry mistake) before the lot can be re-approved through the normal QC flow. The response note is mandatory at re-approval time for returned lots.
- Return reason, response note, and all transitions are audit-trailed.

### Terminology
Button: "Return for Review". Status chip: "Returned". Avoid "kickback" and "recall" (regulatory connotation).

### Touchpoints
- Backend: `lot.py` transition map, return-reason + response-note fields, endpoints for reject/return with reason, re-approval guard requiring response note, audit log entries.
- Frontend: action buttons + reason dialogs on `ReleaseQueue.tsx`, amber card treatment + reason display on Sample Tracker, response-note prompt in the re-approval flow.
- Migration: `return_reason`, `return_response_note` (nullable text) on Lot.

---

## 4. Tab Autoscroll + Sticky Submit (Create Sample tables)

### Requirements
- Applies to **both** the parent-lot sub-batches table and the multi-SKU composite products table.
- When keyboard focus moves to a cell (Tab/Shift+Tab/Enter/auto-new-row), the focused row scrolls into view (`scrollIntoView({block: 'nearest'})` or equivalent).
- The submit button bar becomes **sticky at the bottom of the viewport** so it is always visible regardless of scroll position.

### Touchpoints
- Frontend only: `CreateSample.tsx` keyboard handlers + sticky footer styling.

---

## 5. Create Sample Section Differentiation

### Requirements
- Page canvas darkens relative to cards (light mode: deeper gray, e.g. slate-100/150; dark mode: dragonBlack1).
- Cards stay lighter surfaces with stronger shadow and larger vertical gaps so each section "floats".
- Each section header gets a tinted band + colored icon:
  - Lot Type: blue
  - Lot Details: violet
  - Lab Reference: amber
- Implemented with theme-aware tokens so the treatment works in both light and Kanagawa Dragon dark modes.

### Touchpoints
- Frontend only: `CreateSample.tsx` section containers/headers.
- Sequencing: item 5 ships first in light mode using plain Tailwind classes; item 6 then migrates those classes to semantic tokens along with the rest of the app.

---

## 6. Global Dark Mode: Kanagawa Dragon

### Palette (from rebelot/kanagawa.nvim, dragon variant)
Surfaces (dark → light):
- dragonBlack0 `#0d0c0c` (deepest: modals/float bg)
- dragonBlack1 `#12120f` (page canvas / bg_dim)
- dragonBlack2 `#1D1C19`
- dragonBlack3 `#181616` (main bg)
- dragonBlack4 `#282727` (raised surface)
- dragonBlack5 `#393836` (highest surface / hover)
- dragonBlack6 `#625e5a` (muted borders / nontext)

Text: dragonWhite `#c5c9c5` (primary), dragonGray `#a6a69c` / dragonGray2 `#9e9b93` (secondary), dragonGray3 `#7a8382` (disabled), dragonAsh `#737c73` (faint).

Accents (full Dragon palette applies to semantic colors in dark mode):
- Success / PASS: dragonGreen2 `#8a9a7b` (alt dragonGreen `#87a987`)
- Error / FAIL: dragonRed `#c4746e`
- Warning / amber (incl. Returned cards): dragonYellow `#c4b28a`
- Info / primary blue: dragonBlue2 `#8ba4b0`
- Violet accent: dragonViolet `#8992a7`
- Additional: dragonAqua `#8ea4a2`, dragonTeal `#949fb5`, dragonOrange `#b6927b`, dragonPink `#a292a3`

### Requirements
- Tailwind `dark` class strategy with CSS variables for semantic tokens (surface, surface-raised, border, text-primary, text-secondary, success, error, warning, info, accent).
- Sun/moon toggle in the top header bar; preference persisted in localStorage; **default light**.
- Migrate hardcoded slate/white/status classes across all pages to the semantic tokens.
- **Documents stay light, but dimmed in dark mode:** generated files (COA, COC PDFs, labels) are always pure white; on-screen previews in dark mode get a comfort filter on the preview container (`filter: brightness(0.85) sepia(0.04)`), rendering the paper as a warm dimmed off-white on the dark canvas. No inversion (would distort logos and PASS/FAIL colors). Light mode previews stay unfiltered.
- **All-or-nothing ship:** the toggle only appears once every page renders correctly in Dragon. No half-dark screens.

### Touchpoints
- Frontend: `tailwind.config`, global CSS variables, theme store/hook + header toggle, sweep of all pages/components to tokens.

---

## Testing Notes
- Backend: pytest coverage for new transitions (reject/return + response-note guard), `include_on_coa` filtering in COA generation, COC archive endpoint (incl. legacy-lot fallback), permission checks (Lab Tech denied on reject/return).
- Frontend: Vitest for AdditionalTestsAccordion dropdown/selection, reason dialogs, theme toggle persistence; `npm run build` for type safety.
- Manual: visual pass over every page in dark mode before exposing the toggle.
