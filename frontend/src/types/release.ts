// Release status types
export type ReleaseStatus = "awaiting_release" | "released"

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
}

// Archive item (released COAs with lot_id and product_id)
export interface ArchiveItem {
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
  name: string
  result: string
  unit: string | null
  specification: string
  status: string  // "Pass" or "Fail"
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

  // Notes
  notes: string | null

  // Generation info
  generated_date: string
  released_by: string | null
  released_by_title: string | null
}
