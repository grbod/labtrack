import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactElement } from "react"

vi.mock("@/api/release", () => ({
  releaseApi: {
    getGate: vi.fn(),
    attestSensory: vi.fn(),
  },
}))

import { ReleaseGatePanel } from "./ReleaseGatePanel"
import { releaseApi } from "@/api/release"
import { useAuthStore } from "@/store/auth"
import type { ReleaseGateStatus } from "@/types/release"
import type { User } from "@/types"

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

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
  created_at: "2024-01-01",
  updated_at: null,
}

function makeGate(overrides: Partial<ReleaseGateStatus> = {}): ReleaseGateStatus {
  return {
    lot_id: 1,
    product_id: 2,
    is_legacy_import: false,
    results_all_approved: true,
    missing_tests: [],
    failing_tests: [],
    indeterminate_tests: [],
    sensory_rows: [],
    sensory_all_attested: true,
    blocking_reasons: [],
    can_release: true,
    prior_email_recipients: [],
    prior_email_date: null,
    ...overrides,
  }
}

describe("ReleaseGatePanel", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: qcUser, isAuthenticated: true })
    vi.mocked(releaseApi.getGate).mockReset()
    vi.mocked(releaseApi.attestSensory).mockReset()
  })

  it("shows an all-clear banner when there are no blocking or amber issues", async () => {
    vi.mocked(releaseApi.getGate).mockResolvedValue(makeGate())
    renderWithQuery(<ReleaseGatePanel lotId={1} productId={2} isReleased={false} />)

    expect(await screen.findByText("All release gate checks passed")).toBeInTheDocument()
  })

  it("lists missing and failing tests as blocking issues", async () => {
    vi.mocked(releaseApi.getGate).mockResolvedValue(
      makeGate({
        can_release: false,
        missing_tests: ["Salmonella spp."],
        failing_tests: [{ name: "Lead", result_value: "12 ppm", spec_text: "< 10 ppm" }],
      })
    )
    renderWithQuery(<ReleaseGatePanel lotId={1} productId={2} isReleased={false} />)

    expect(await screen.findByText("Blocking Issues")).toBeInTheDocument()
    expect(screen.getByText("Missing: Salmonella spp.")).toBeInTheDocument()
    expect(screen.getByText(/Lead: 12 ppm \(spec: < 10 ppm\)/)).toBeInTheDocument()
    expect(screen.queryByText("All release gate checks passed")).not.toBeInTheDocument()
  })

  it("lets a QC manager check an unattested sensory row and confirm", async () => {
    vi.mocked(releaseApi.getGate).mockResolvedValue(
      makeGate({
        sensory_all_attested: false,
        sensory_rows: [
          { lab_test_type_id: 9, name: "Organoleptic Evaluation", spec_text: "Conforms", attested: false },
        ],
      })
    )
    vi.mocked(releaseApi.attestSensory).mockResolvedValue(makeGate({ sensory_rows: [], sensory_all_attested: true }))

    renderWithQuery(<ReleaseGatePanel lotId={1} productId={2} isReleased={false} />)

    const checkbox = await screen.findByRole("checkbox")
    expect(checkbox).not.toBeChecked()

    const confirmButton = screen.getByRole("button", { name: /confirm attestation/i })
    expect(confirmButton).toBeDisabled()

    fireEvent.click(checkbox)
    expect(confirmButton).toBeEnabled()

    fireEvent.click(confirmButton)

    await waitFor(() => {
      expect(releaseApi.attestSensory).toHaveBeenCalledWith(1, 2, [9])
    })
  })
})
