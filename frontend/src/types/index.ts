// User roles
export type UserRole = "ADMIN" | "QC_MANAGER" | "LAB_TECH" | "READ_ONLY"

// Lot types and statuses
export type LotType = "STANDARD" | "PARENT_LOT" | "SUBLOT" | "MULTI_SKU_COMPOSITE"
export type LotStatus = "PENDING" | "TESTED" | "APPROVED" | "RELEASED" | "REJECTED"
export type TestResultStatus = "DRAFT" | "REVIEWED" | "APPROVED"

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

// Product types
export interface Product {
  id: number
  brand: string
  product_name: string
  flavor: string | null
  size: string | null
  display_name: string
  serving_size: number | null
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
  created_at: string
  updated_at: string | null
}

export interface ProductInLot {
  id: number
  display_name: string
  brand: string
  percentage: number | null
}

export interface LotWithProducts extends Lot {
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
