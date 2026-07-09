// User roles (lowercase to match backend)
export type UserRole = "admin" | "qc_manager" | "lab_tech" | "read_only"

// Lot types and statuses (lowercase to match backend enum values)
export type LotType = "standard" | "parent_lot" | "sublot" | "multi_sku_composite"
export type LotStatus = "awaiting_results" | "partial_results" | "needs_attention" | "under_review" | "awaiting_release" | "approved" | "released" | "rejected"
export type TestResultStatus = "draft" | "reviewed" | "approved"

// User type
export interface User {
  id: number
  username: string
  email: string | null
  full_name: string | null
  title: string | null
  phone: string | null
  signature_url: string | null
  role: UserRole
  is_active: boolean
  created_at: string
  updated_at: string | null
}

// User profile update
export interface UserProfileUpdate {
  full_name?: string | null
  title?: string | null
  phone?: string | null
  email?: string | null
}

// Auth types
export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface LoginCredentials {
  username: string
  password: string
}

// Product size variant
export interface ProductSize {
  id: number
  size: string
}

// Product types
export interface Product {
  id: number
  brand: string
  product_name: string
  flavor: string | null
  size: string | null  // Legacy single size field (for backward compatibility)
  sizes: ProductSize[]  // Multiple size variants
  display_name: string
  serving_size: string | null  // e.g., "30g", "2 capsules", "1 tsp"
  expiry_duration_months: number
  version: string | null  // e.g., "v1", "v2.1"
  is_active: boolean
  archived_at: string | null
  archived_by_id: number | null
  archive_reason: string | null
  created_at: string
  updated_at: string | null
}

// Product test specification
export interface ProductTestSpecification {
  id: number
  lab_test_type_id: number
  test_name: string
  test_category: string | null
  test_method: string | null
  test_unit: string | null
  specification: string
  is_required: boolean
}

export interface ProductWithSpecs extends Product {
  test_specifications: ProductTestSpecification[]
}

// Product summary for lot list responses (Kanban cards)
export interface ProductSummary {
  id: number
  brand: string
  product_name: string
  flavor: string | null
  size: string | null
  percentage: number | null
  batch_number: string | null
}

// Minimal sublot info for parent-lot list/card responses
export interface SublotSummary {
  sublot_number: string
  production_date?: string | null
}

// Lot types
export interface Lot {
  id: number
  lot_number: string
  lot_type: LotType
  reference_number: string
  mfg_date: string | null
  exp_date: string | null
  status: LotStatus
  generate_coa: boolean
  rejection_reason: string | null
  attached_pdfs: Array<string | Record<string, unknown>> | null  // Legacy strings or attachment objects
  has_pending_retest: boolean  // True when retest is pending
  coc_storage_key: string | null
  return_reason: string | null
  return_response_note: string | null
  created_at: string
  updated_at: string | null
  products?: ProductSummary[]  // Included in list responses for Kanban display
  sublots?: SublotSummary[]  // Parent-lot sublots (empty/absent for other lot types)
  tests_entered?: number  // Count of test results with values entered
  tests_total?: number  // Total expected tests from product specs
  tests_failed?: number  // Count of test results that failed specification
}

export interface LotStatusRecalculationChange {
  lot_id: number
  reference_number: string
  lot_number: string
  old_status: LotStatus
  new_status: LotStatus
  reason: string
  missing_tests: string[]
  failing_tests: string[]
}

export interface LotStatusRecalculationResponse {
  mode: "preview" | "apply"
  scanned_count: number
  changed_count: number
  changes: LotStatusRecalculationChange[]
}

export interface ProductInLot {
  id: number
  display_name: string
  brand: string
  percentage: number | null
  batch_number: string | null
}

export interface LotWithProducts extends Omit<Lot, 'products'> {
  products: ProductInLot[]
}

// Test result types
export interface TestResult {
  id: number
  lot_id: number
  test_type: string
  result_value: string | null
  unit: string | null
  test_date: string | null
  pdf_source: string | null
  confidence_score: number | null
  status: TestResultStatus
  specification: string | null
  method: string | null
  notes: string | null
  approved_by_id: number | null
  approved_at: string | null
  created_at: string
  updated_at: string | null
  lab_test_type_id: number | null
  include_on_coa: boolean
  // Extended fields
  lot_number?: string
  lot_reference?: string
  // True when the current user both entered and approved this result
  self_approval_warning?: boolean
}

export type ResultImportStatus =
  | "processing"
  | "needs_confirmation"
  | "confirmed"
  | "failed"
  | "cancelled"
  | "reverted"

export interface ExtractedResultRow {
  row_id: string
  test_name_raw: string
  test_name_normalized: string
  result_value_raw: string | null
  unit_raw: string | null
  target_unit: string | null
  limit_raw: string | null
  test_date: string | null
  received_date: string | null
  confidence: number
  warnings: string[]
  metadata: Record<string, unknown>
  matched_lab_test_type_id: number | null
  match_source?: "exact" | "builtin_alias" | "approved_alias" | "fuzzy" | "unmatched" | null
  alias_id?: number | null
}

export interface ResultExtraction {
  identifiers: Array<{ type: string; value: string; confidence: number }>
  lab_name: string | null
  date_tested: string | null
  report_date: string | null
  received_date: string | null
  rows: ExtractedResultRow[]
  warnings: string[]
}

export interface ResultImportCandidate {
  lot_id: number
  reference_number: string
  lot_number: string
  status: LotStatus
  score: number
  reasons: string[]
  products: string[]
}

export interface ResultImport {
  id: number
  original_filename: string
  storage_key: string | null
  file_hash: string
  status: ResultImportStatus
  extracted_data: ResultExtraction | null
  match_candidates: ResultImportCandidate[] | null
  warnings: string[] | null
  error_message: string | null
  selected_lot_id: number | null
  uploaded_by_id: number | null
  confirmed_by_id: number | null
  confirmed_at: string | null
  openrouter_model: string | null
  usage_metadata: Record<string, unknown> | null
  duplicate_of_id: number | null
  duplicate_summary: DuplicateImportSummary | null
  created_at: string
  updated_at: string
}

export interface DuplicateImportSummary {
  import_id: number
  original_filename: string
  confirmed_at: string | null
  confirmed_by: string | null
  lot_id: number | null
  reference_number: string | null
  lot_number: string | null
}

export interface ResultImportUploadResponse {
  items: ResultImport[]
  duplicates: ResultImport[]
}

export interface LinkCandidate {
  lot_id: number
  reference_number: string
  lot_number: string
  status: LotStatus
  products: string[]
}

export interface ResultRowAction {
  row_id: string
  action: "apply" | "replace" | "skip" | "create_adhoc"
  test_result_id?: number | null
  lab_test_type_id?: number | null
  test_name?: string | null
  result_value?: string | null
  unit?: string | null
  specification?: string | null
  method?: string | null
}

export interface ExistingResultPreview {
  id: number
  test_type: string
  result_value: string | null
  unit: string | null
  status: TestResultStatus
  test_date: string | null
  pdf_source: string | null
}

export interface ResultImportRowPreview {
  row_id: string
  resolved_test_name: string | null
  unit: string | null
  specification: string | null
  method: string | null
  lab_test_type_id: number | null
  requires_lab_test_mapping: boolean
  suggested_action: "apply" | "replace" | "skip" | "create_adhoc"
  warnings: string[]
  existing_result: ExistingResultPreview | null
}

export interface ResultImportPreview {
  import_id: number
  lot_id: number
  rows: ResultImportRowPreview[]
}

export interface ResultImportPreviewOverride {
  row_id: string
  lab_test_type_id: number | null
}

export interface ConfirmResultImportRequest {
  lot_id: number
  row_actions: ResultRowAction[]
}

export interface ConfirmResultImportResponse {
  import_id: number
  lot_id: number
  created_result_ids: number[]
  updated_result_ids: number[]
  skipped_row_ids: string[]
  status: ResultImportStatus
  /** Pending test-name alias suggestions recorded during confirm (optional;
   *  older backends omit it, treat as 0). */
  alias_suggestions_created?: number
}

// Lab test type
export interface LabTestType {
  id: number
  test_name: string
  test_category: string
  default_unit: string | null
  description: string | null
  test_method: string | null
  abbreviations: string | null
  default_specification: string | null
  is_active: boolean
  archived_at: string | null
  archived_by_id: number | null
  archive_reason: string | null
  created_at: string
  updated_at: string | null
}

export interface LabTestAlias {
  id: number
  raw_phrase: string
  normalized_key: string
  lab_name: string | null
  lab_test_type_id: number
  target_test_name: string | null
  target_test_category: string | null
  target_default_unit: string | null
  target_default_specification: string | null
  target_test_method: string | null
  status: "pending" | "approved" | "disabled"
  source: "fuzzy" | "manual_override" | string
  suggestion_count: number
  first_seen_at: string | null
  last_seen_at: string | null
  last_result_import_id: number | null
  last_lot_id: number | null
  last_filename: string | null
  last_suggested_by_id: number | null
  approved_by_id: number | null
  approved_at: string | null
  disabled_by_id: number | null
  disabled_at: string | null
  disable_reason: string | null
  created_at: string
  updated_at: string
}

export interface LabTestAliasList {
  items: LabTestAlias[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface LabTestBuiltinAlias {
  raw_phrase: string
  normalized_key: string
  lab_test_type_id: number | null
  target_test_name: string
  target_test_category: string | null
  target_default_unit: string | null
  target_default_specification: string | null
  target_test_method: string | null
}

export interface LabTestBuiltinAliasList {
  items: LabTestBuiltinAlias[]
  total: number
}

export interface LabTestTypeCategoryCount {
  category: string
  count: number
}

// Daane Labs test mapping
export interface DaaneTestMappingItem {
  lab_test_type_id: number
  test_name: string
  test_method: string | null
  default_unit: string | null
  daane_method: string | null
  match_type: string
  match_reason: string | null
}

export interface DaaneTestMappingListResponse {
  items: DaaneTestMappingItem[]
  total: number
}

// API response types
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Extended types for Sample Modal with test specifications

/** Test specification from product (used in modal) */
export interface TestSpecInProduct {
  id: number
  lab_test_type_id: number
  test_name: string
  test_category: string | null
  test_method: string | null
  test_unit: string | null
  specification: string
  is_required: boolean
}

/** Product with test specifications for modal display */
export interface ProductInLotWithSpecs {
  id: number
  brand: string
  product_name: string
  flavor: string | null
  size: string | null
  display_name: string
  serving_size: string | null
  percentage: number | null
  batch_number: string | null
  test_specifications: TestSpecInProduct[]
}

/** Lot with full product details and test specifications */
export interface LotWithProductSpecs extends Lot {
  products: ProductInLotWithSpecs[]
}

/** Test result row with validation state for modal table */
export interface TestResultRow extends TestResult {
  specificationObj?: TestSpecInProduct
  passFailStatus: 'pass' | 'fail' | 'pending' | null
  isFlagged: boolean
  isAdditionalTest: boolean
}

/** Filter status for test results table */
export type TestFilterStatus = 'all' | 'pending' | 'passed' | 'failed'

// Customer types
export interface Customer {
  id: number
  company_name: string
  contact_name: string
  email: string
  is_active: boolean
  archived_at: string | null
  archived_by_id: number | null
  archive_reason: string | null
  created_at: string
  updated_at: string | null
}

// Archive request type
export interface ArchiveRequest {
  reason: string
}

// COA Category Order types
export interface COACategoryOrder {
  id: number
  category_order: string[]
  created_at: string
  updated_at: string | null
}

// Audit types
export type AuditAction = 'insert' | 'update' | 'delete' | 'approve' | 'reject' | 'override'

export interface AuditLogEntry {
  id: number
  action: AuditAction
  timestamp: string
  user_id: number | null
  username: string | null
  old_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  changes: Record<string, { from: unknown; to: unknown }>
  reason: string | null
  ip_address: string | null
  table_name: string
  record_id: number
}

export interface AuditHistoryResponse {
  items: AuditLogEntry[]
  total: number
  table_name: string
  record_id: number
}

export interface LotAuditHistoryResponse {
  items: AuditLogEntry[]
  total: number
  lot_id: number
  tables_included: string[]
}

// Archived lot types
export interface ArchivedLot {
  lot_id: number
  product_id: number
  reference_number: string
  lot_number: string
  product_name: string
  brand: string
  flavor: string | null
  size: string | null
  status: 'released' | 'rejected'
  completed_at: string
  customer_name: string | null
  rejection_reason: string | null
}

// Retest types
export type RetestStatus = 'pending' | 'completed' | 'review_required'

export interface RetestItem {
  id: number
  test_result_id: number
  original_value: string | null
  current_value: string | null
  test_type: string | null
}

export interface RetestRequest {
  id: number
  lot_id: number
  reference_number: string
  retest_number: number
  reason: string
  status: RetestStatus
  requested_by_id: number
  requested_by_name: string | null
  completed_at: string | null
  created_at: string
  items: RetestItem[]
}

export interface RetestRequestListResponse {
  items: RetestRequest[]
  total: number
}

export interface CreateRetestRequestData {
  test_result_ids: number[]
  reason: string
}

export interface RetestOriginalValue {
  test_result_id: number
  original_value: string | null
  retest_reference: string
  retest_status: RetestStatus
}

export interface ReviewThreadEvent {
  type: "return" | "resolution"
  message: string
  author: string | null
  author_role: string | null
  at: string
}

export interface ReviewThreadResponse {
  events: ReviewThreadEvent[]
  return_count: number
}
