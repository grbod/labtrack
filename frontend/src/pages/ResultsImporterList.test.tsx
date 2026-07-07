import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactElement } from "react"

// --- Module mocks -----------------------------------------------------------
// react-pdf renders a real PDF via a web worker; stub it out so the modal's
// left pane mounts without touching pdfjs. The two CSS side-effect imports are
// stubbed too (jsdom has no styling and vite would otherwise resolve them).
vi.mock("react-pdf", () => ({
  Document: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="pdf-document">{children}</div>
  ),
  Page: () => <div data-testid="pdf-page" />,
  pdfjs: { GlobalWorkerOptions: { workerSrc: "" }, version: "test" },
}))
vi.mock("react-pdf/dist/Page/AnnotationLayer.css", () => ({}))
vi.mock("react-pdf/dist/Page/TextLayer.css", () => ({}))

// API layer mocks — the page/modal go through TanStack Query hooks, which call
// these axios-backed API modules. Mocking the API (not the hooks) exercises the
// real query wiring.
vi.mock("@/api/resultImports", () => ({
  resultImportsApi: {
    list: vi.fn(),
    get: vi.fn(),
    preview: vi.fn(),
    linkCandidates: vi.fn(),
    confirm: vi.fn(),
    retry: vi.fn(),
    cancel: vi.fn(),
    revert: vi.fn(),
    getPdfBlob: vi.fn(),
  },
}))
vi.mock("@/api/labTestTypes", () => ({
  labTestTypesApi: { list: vi.fn() },
}))
vi.mock("@/api/lots", () => ({
  lotsApi: { getWithSpecs: vi.fn() },
}))
vi.mock("@/api/testResults", () => ({
  testResultsApi: { list: vi.fn() },
}))

import { ResultsImporterListPage } from "./ResultsImporterList"
import { resultImportsApi } from "@/api/resultImports"
import { labTestTypesApi } from "@/api/labTestTypes"
import { lotsApi } from "@/api/lots"
import { testResultsApi } from "@/api/testResults"
import { useAuthStore } from "@/store/auth"
import type {
  LabTestType,
  ResultImport,
  ResultImportPreview,
  User,
} from "@/types"

// --- jsdom polyfills Radix Dialog + react-pdf preview rely on ----------------
beforeEach(() => {
  const proto = window.HTMLElement.prototype as unknown as Record<string, unknown>
  proto.hasPointerCapture = proto.hasPointerCapture || (() => false)
  proto.setPointerCapture = proto.setPointerCapture || (() => {})
  proto.releasePointerCapture = proto.releasePointerCapture || (() => {})
  proto.scrollIntoView = proto.scrollIntoView || (() => {})

  if (!("ResizeObserver" in window)) {
    ;(window as unknown as Record<string, unknown>).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (!URL.createObjectURL) URL.createObjectURL = () => "blob:mock"
  if (!URL.revokeObjectURL) URL.revokeObjectURL = () => {}
})

// --- Fixtures ---------------------------------------------------------------
const PANEL_LAB_TYPE_ID = 100

const qcUser: User = {
  id: 1,
  username: "qcmanager",
  email: "qc@example.com",
  full_name: "QC Manager",
  title: null,
  phone: null,
  signature_url: null,
  role: "qc_manager",
  is_active: true,
  created_at: "2026-01-01",
  updated_at: null,
}

const labTypes: LabTestType[] = [
  {
    id: PANEL_LAB_TYPE_ID,
    test_name: "Total Plate Count",
    test_category: "Micro",
    default_unit: "CFU/g",
    description: null,
    test_method: "USP <2021>",
    abbreviations: "TPC",
    is_active: true,
    archived_at: null,
    archived_by_id: null,
    archive_reason: null,
    default_specification: "Negative",
    created_at: "2026-01-01",
    updated_at: null,
  } as LabTestType,
]

function makeImport(id: number, overrides: Partial<ResultImport> = {}): ResultImport {
  const lotId = 500 + id
  return {
    id,
    original_filename: `coa-${id}.pdf`,
    storage_key: `store/coa-${id}.pdf`,
    file_hash: `hash-${id}`,
    status: "needs_confirmation",
    extracted_data: {
      identifiers: [],
      lab_name: "Test Lab",
      date_tested: null,
      report_date: null,
      received_date: null,
      warnings: [],
      rows: [
        {
          row_id: `r-${id}`,
          test_name_raw: "Total Plate Count",
          test_name_normalized: "Total Plate Count",
          result_value_raw: "Negative",
          unit_raw: "CFU/g",
          target_unit: "CFU/g",
          limit_raw: "Negative",
          test_date: null,
          received_date: null,
          confidence: 0.95,
          warnings: [],
          metadata: {},
          matched_lab_test_type_id: PANEL_LAB_TYPE_ID,
          match_source: "exact",
        },
      ],
    },
    match_candidates: [
      {
        lot_id: lotId,
        reference_number: `REF-00${id}`,
        lot_number: `LOT-00${id}`,
        status: "awaiting_results",
        score: 0.9,
        reasons: ["Reference number match"],
        products: ["Brand X Product"],
      },
    ],
    warnings: null,
    error_message: null,
    selected_lot_id: null,
    uploaded_by_id: 1,
    confirmed_by_id: null,
    confirmed_at: null,
    openrouter_model: null,
    usage_metadata: null,
    duplicate_of_id: null,
    duplicate_summary: null,
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
    ...overrides,
  }
}

function lotWithSpecs(lotId: number, ref: string) {
  return {
    id: lotId,
    lot_number: `LOT-${lotId}`,
    reference_number: ref,
    lot_type: "standard",
    status: "awaiting_results",
    products: [
      {
        id: 1,
        brand: "Brand X",
        product_name: "Product",
        flavor: null,
        size: null,
        display_name: "Brand X Product",
        serving_size: null,
        percentage: null,
        batch_number: null,
        test_specifications: [
          {
            id: 1,
            lab_test_type_id: PANEL_LAB_TYPE_ID,
            test_name: "Total Plate Count",
            test_category: "Micro",
            test_method: "USP <2021>",
            test_unit: "CFU/g",
            specification: "Negative",
            is_required: true,
          },
        ],
      },
    ],
  }
}

function previewFor(id: number, lotId: number): ResultImportPreview {
  return {
    import_id: id,
    lot_id: lotId,
    rows: [
      {
        row_id: `r-${id}`,
        resolved_test_name: "Total Plate Count",
        unit: "CFU/g",
        specification: "Negative",
        method: "USP <2021>",
        lab_test_type_id: PANEL_LAB_TYPE_ID,
        requires_lab_test_mapping: false,
        suggested_action: "apply",
        warnings: [],
        existing_result: null,
      },
    ],
  }
}

const page = <T,>(items: T[]) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 25,
  total_pages: 1,
})

/** Wire the mocked API modules to serve the given list of imports. */
function seedApi(imports: ResultImport[]) {
  const byId = new Map(imports.map((imp) => [imp.id, imp]))
  vi.mocked(resultImportsApi.list).mockResolvedValue(page(imports))
  vi.mocked(resultImportsApi.get).mockImplementation(async (id: number) => {
    const found = byId.get(id)
    if (!found) throw new Error("not found")
    return found
  })
  vi.mocked(resultImportsApi.preview).mockImplementation(
    async (id: number, lotId: number) => previewFor(id, lotId)
  )
  vi.mocked(resultImportsApi.getPdfBlob).mockResolvedValue(new Blob(["%PDF"]))
  vi.mocked(resultImportsApi.linkCandidates).mockResolvedValue([])
  vi.mocked(resultImportsApi.confirm).mockImplementation(async (id: number, payload) => ({
    import_id: id,
    lot_id: payload.lot_id,
    created_result_ids: [999],
    updated_result_ids: [],
    skipped_row_ids: [],
    status: "confirmed" as const,
  }))
  vi.mocked(resultImportsApi.cancel).mockImplementation(async (id: number) => ({
    ...byId.get(id)!,
    status: "cancelled" as const,
  }))
  vi.mocked(resultImportsApi.revert).mockImplementation(async (id: number) => ({
    ...byId.get(id)!,
    status: "reverted" as const,
  }))

  vi.mocked(labTestTypesApi.list).mockResolvedValue(page(labTypes))
  vi.mocked(lotsApi.getWithSpecs).mockImplementation(async (lotId: number) => {
    const ref = imports.find((i) => 500 + i.id === lotId)?.match_candidates?.[0]?.reference_number
    return lotWithSpecs(lotId, ref || "REF") as never
  })
  vi.mocked(testResultsApi.list).mockResolvedValue(page([]))
}

function renderPage(ui: ReactElement = <ResultsImporterListPage />) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  useAuthStore.setState({ user: qcUser, isAuthenticated: true })
})

afterEach(() => {
  vi.clearAllMocks()
})

/** The review modal, scoped by its (sr-only) title = the import's filename. */
function reviewDialog(filename: string) {
  return screen.getByRole("dialog", { name: filename })
}

describe("ResultsImporterListPage", () => {
  it("opens the review modal on row click and closes it via the X button", async () => {
    seedApi([makeImport(1)])
    renderPage()

    // Row renders once the list query resolves.
    const fileCell = await screen.findByText("coa-1.pdf")
    fireEvent.click(fileCell)

    // Modal opens; its accessible name is the filename (sr-only DialogTitle).
    const dialog = await waitFor(() => reviewDialog("coa-1.pdf"))
    // Status label shows in both the modal header and the review-pane header.
    expect(within(dialog).getAllByText("Needs review").length).toBeGreaterThan(0)

    // Close via the header X (aria-label="Close").
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }))
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "coa-1.pdf" })).not.toBeInTheDocument()
    )
  })

  it("navigates the review queue with the prev/next chevrons", async () => {
    seedApi([makeImport(1), makeImport(2)])
    renderPage()

    fireEvent.click(await screen.findByText("coa-1.pdf"))
    const dialog1 = await waitFor(() => reviewDialog("coa-1.pdf"))
    expect(within(dialog1).getByText("1 of 2 to review")).toBeInTheDocument()

    // Next chevron -> import 2 becomes the active import.
    fireEvent.click(within(dialog1).getByRole("button", { name: "Next import to review" }))
    const dialog2 = await waitFor(() => reviewDialog("coa-2.pdf"))
    expect(within(dialog2).getByText("2 of 2 to review")).toBeInTheDocument()

    // Prev chevron -> back to import 1.
    fireEvent.click(within(dialog2).getByRole("button", { name: "Previous import to review" }))
    await waitFor(() => reviewDialog("coa-1.pdf"))
    expect(within(reviewDialog("coa-1.pdf")).getByText("1 of 2 to review")).toBeInTheDocument()
  })

  it("advances to the next needs_confirmation import after Apply", async () => {
    seedApi([makeImport(1), makeImport(2)])
    renderPage()

    fireEvent.click(await screen.findByText("coa-1.pdf"))
    const dialog1 = await waitFor(() => reviewDialog("coa-1.pdf"))

    // Apply enables only once preview + lot specs + lot results have all loaded.
    const applyBtn = await within(dialog1).findByRole(
      "button",
      { name: /Apply .*as Drafts/ },
      { timeout: 3000 }
    )
    await waitFor(() => expect(applyBtn).toBeEnabled(), { timeout: 3000 })
    fireEvent.click(applyBtn)

    // Modal stays open, now showing import 2.
    await waitFor(() => reviewDialog("coa-2.pdf"))
    expect(resultImportsApi.confirm).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ lot_id: 501 })
    )
  })

  it("closes the modal after Apply when it was the last import in the queue", async () => {
    // Only one needs_confirmation import in the queue.
    seedApi([makeImport(1), makeImport(3, { status: "confirmed", confirmed_by_id: 1 })])
    renderPage()

    fireEvent.click(await screen.findByText("coa-1.pdf"))
    const dialog = await waitFor(() => reviewDialog("coa-1.pdf"))

    const applyBtn = await within(dialog).findByRole(
      "button",
      { name: /Apply .*as Drafts/ },
      { timeout: 3000 }
    )
    await waitFor(() => expect(applyBtn).toBeEnabled(), { timeout: 3000 })
    fireEvent.click(applyBtn)

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "coa-1.pdf" })).not.toBeInTheDocument()
    )
    expect(resultImportsApi.confirm).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ lot_id: 501 })
    )
  })

  it("closes the modal when Cancel is confirmed", async () => {
    seedApi([makeImport(1)])
    renderPage()

    fireEvent.click(await screen.findByText("coa-1.pdf"))
    const dialog = await waitFor(() => reviewDialog("coa-1.pdf"))

    // Review-pane Cancel opens the confirm dialog.
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }))
    const confirmBtn = await screen.findByRole("button", { name: "Cancel import" })
    fireEvent.click(confirmBtn)

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "coa-1.pdf" })).not.toBeInTheDocument()
    )
    expect(vi.mocked(resultImportsApi.cancel).mock.calls[0][0]).toBe(1)
  })
})
