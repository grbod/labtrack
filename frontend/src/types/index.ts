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
  role: UserRole
  is_active: boolean
  created_at: string
  updated_at: string | null
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
  created_at: string
  updated_at: string | null
  products?: ProductSummary[]  // Included in list responses for Kanban display
  tests_entered?: number  // Count of test results with values entered
  tests_total?: number  // Total expected tests from product specs
  tests_failed?: number  // Count of test results that failed specification
}

export interface ProductInLot {
  id: number
  display_name: string
  brand: string
  percentage: number | null
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
  // Extended fields
  lot_number?: string
  lot_reference?: string
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
  created_at: string
  updated_at: string | null
}

export interface LabTestTypeCategoryCount {
  category: string
  count: number
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
  percentage: number | null
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
  created_at: string
  updated_at: string | null
}
