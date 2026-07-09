// Release status types
export type ReleaseStatus = "awaiting_release" | "released" | "forked"

// Customer type
export interface Customer {
  id: number
  company_name: string
  contact_name: string | null
  email: string | null
  phone: string | null
  address: string | null
  created_at: string
  updated_at: string | null
}

// Queue item for listing releases (Lot+Product based)
export interface ReleaseQueueItem {
  lot_id: number
  product_id: number
  reference_number: string
  lot_number: string
  product_name: string
  brand: string
  flavor: string | null
  size: string | null
  created_at: string
  // Per-member release status. "forked" members were individualized out of a
  // composite and are not actionable in the queue.
  release_status?: ReleaseStatus
  forked_to_lot_id?: number | null
  forked_to_reference?: string | null
}

// Archive item (released COAs with lot_id and product_id)
export interface ArchiveItem {
  id: number // COARelease id - required to void a release
  lot_id: number
  product_id: number
  reference_number: string
  lot_number: string
  product_name: string
  brand: string
  flavor: string | null
  size: string | null
  released_at: string
  customer_name: string | null
  // Post-release supersede: the re-sample fork COA that replaced this one.
  superseded_by_release_id?: number | null
  superseded_by_reference?: string | null
}

// Legacy queue item type (deprecated, use ReleaseQueueItem or ArchiveItem)
export interface COAReleaseQueueItem {
  id: number
  reference_number: string
  product_name: string
  brand: string
  created_at: string
  status: ReleaseStatus
}

// Release details for a Lot+Product combination
export interface ReleaseDetails {
  lot_id: number
  product_id: number
  customer_id: number | null
  notes: string | null
  status: ReleaseStatus
  released_at: string | null
  draft_data: { customer_id?: number; notes?: string } | null
  lot: {
    lot_number: string
    reference_number: string
    mfg_date: string | null
    exp_date: string | null
  }
  product: {
    id: number
    product_name: string
    brand: string
    flavor: string | null
    size: string | null
    display_name: string
  }
  customer: Customer | null
  source_pdfs: string[]
  // Fork lineage: set when this member was forked out (status === "forked").
  forked_to_lot_id?: number | null
  forked_to_reference?: string | null
}

// Legacy release type (deprecated, use ReleaseDetails)
export interface COARelease {
  id: number
  lot_id: number
  product_id: number
  customer_id: number | null
  notes: string | null
  status: ReleaseStatus
  released_at: string | null
  coa_file_path: string | null
  draft_data: { customer_id?: number; notes?: string } | null
  lot: {
    lot_number: string
    reference_number: string
    mfg_date: string | null
    exp_date: string | null
  }
  product: {
    id: number
    product_name: string
    brand: string
    flavor: string | null
    size: string | null
    display_name: string
  }
  customer: Customer | null
  source_pdfs: string[]
}

// Email history for a release
export interface EmailHistory {
  id: number
  recipient_email: string
  sent_at: string
  sent_by: string
}

// Archive filter parameters
export interface ArchiveFilters {
  search?: string
  product_id?: number
  customer_id?: number
  date_from?: string
  date_to?: string
  lot_number?: string
  page?: number
  page_size?: number
  sort_by?: 'released_at' | 'reference_number' | 'lot_number' | 'brand' | 'product_name'
  sort_order?: 'asc' | 'desc'
}

// Draft save data
export interface SaveDraftData {
  customer_id?: number | null
  notes?: string | null
  mfg_date?: string | null  // ISO date string
  exp_date?: string | null  // ISO date string
}

// Create customer data
export interface CreateCustomerData {
  company_name: string
  contact_name?: string
  email?: string
}

// COA Preview Data types
export interface COATestResult {
  id?: number  // Test result ID for retest original value matching
  name: string
  method?: string | null  // TestResult.method (e.g. "USP <2021>")
  result: string
  unit: string | null
  specification: string | null  // null when no spec exists -> render "—"; never fabricated
  status: string  // "Pass", "Fail", or "—"
  verdict?: string | null  // machine-readable verdict kind
}

export interface COANotTestedRow {
  name: string
  method?: string | null
  specification?: string | null
  status: string  // "Not Tested"
}

export interface COAPreviewData {
  // Company info
  company_name: string | null
  company_address: string | null
  company_phone: string | null
  company_email: string | null
  company_logo_url: string | null

  // Product info
  product_name: string
  brand: string

  // Lot info
  lot_number: string
  reference_number: string
  mfg_date: string | null  // Formatted date string
  exp_date: string | null  // Formatted date string

  // Test results
  tests: COATestResult[]
  not_tested: COANotTestedRow[]

  // Document identity + deviation note (release-gate override, if any)
  document_id?: string | null
  deviation_note?: string | null

  // Notes
  notes: string | null

  // Generation info
  generated_date: string
  released_by: string | null
  released_by_title: string | null
  released_by_email: string | null
  signature_url: string | null  // URL to signature image for COA
  released_at: string | null  // Release date (if different from generated_date)

  // Snapshot provenance (present when served from an immutable snapshot)
  source?: string  // "live" | "snapshot"
  reconstructed?: boolean  // backfilled from the register (no serial)
  voided?: boolean  // viewing a voided/superseded snapshot from history
  revision?: number | null
}

// --- Release gate ---------------------------------------------------------

// A test row referenced by the gate (failing / indeterminate)
export interface GateTestRef {
  name: string
  result_value: string | null
  spec_text: string | null
}

// A sensory/organoleptic panel row requiring attestation
export interface GateSensoryRow {
  lab_test_type_id: number
  name: string
  spec_text: string | null
  attested: boolean
}

// A sibling released COA on the same composite lot (for the void prompt)
export interface ReleaseSibling {
  id: number
  product_id: number
  product_name: string | null
  brand: string | null
  reference_number: string | null
}

// Green/amber/red gate summary for releasing a (lot, product) COA
export interface ReleaseGateStatus {
  lot_id: number
  product_id: number
  is_legacy_import: boolean
  results_all_approved: boolean
  // True when this lot is a multi-SKU composite (member view).
  is_composite: boolean
  // Red (blocking) items
  missing_tests: string[]
  failing_tests: GateTestRef[]
  // Composite-only: union of all members' required tests not yet covered by the
  // shared results. A missing union test blocks EVERY member.
  union_missing_tests: string[]
  // Amber (non-blocking) warnings
  indeterminate_tests: GateTestRef[]
  // Sensory attest checklist
  sensory_rows: GateSensoryRow[]
  sensory_all_attested: boolean
  // Overall
  blocking_reasons: string[]
  can_release: boolean
  // Re-release notice: populated when a prior release for this pair was voided
  // and had email history
  prior_email_recipients: string[]
  prior_email_date: string | null
}

// Structured 409 body returned when approve is blocked by the release gate
export interface GateBlockedDetail {
  code: string
  reason: string
  missing_tests: string[]
  failing_tests: string[]
}
