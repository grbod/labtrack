import { useState } from "react"
import { AlertTriangle, CheckCircle2, Info, Loader2, ShieldCheck } from "lucide-react"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { useReleaseGate, useAttestSensory } from "@/hooks/useRelease"
import { useAuthStore } from "@/store/auth"
import type { GateSensoryRow } from "@/types/release"

interface ReleaseGatePanelProps {
  lotId: number
  productId: number
  isReleased: boolean
}

interface SensoryChecklistProps {
  lotId: number
  productId: number
  sensoryRows: GateSensoryRow[]
  canAttest: boolean
  isReleased: boolean
}

/** Sensory attest checklist. Keyed by the server's attested set so a fresh gate
 *  (initial load, after a void/re-release, or after a successful attest) resets
 *  the local "pending" checkbox state without needing an effect. */
function SensoryChecklist({ lotId, productId, sensoryRows, canAttest, isReleased }: SensoryChecklistProps) {
  const attestSensory = useAttestSensory()
  const [checkedIds, setCheckedIds] = useState<number[]>(() =>
    sensoryRows.filter((row) => row.attested).map((row) => row.lab_test_type_id)
  )

  const attestedIds = new Set(sensoryRows.filter((row) => row.attested).map((row) => row.lab_test_type_id))
  const hasUnsavedAttestations = checkedIds.some((id) => !attestedIds.has(id))

  const toggleRow = (id: number, attested: boolean) => {
    if (attested || !canAttest || isReleased) return
    setCheckedIds((prev) => (prev.includes(id) ? prev.filter((existing) => existing !== id) : [...prev, id]))
  }

  const handleConfirmAttestation = () => {
    attestSensory.mutate({ lotId, productId, labTestTypeIds: checkedIds })
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-center gap-1.5 text-[12px] font-semibold text-slate-600">
        <ShieldCheck className="h-3.5 w-3.5" />
        Sensory Attestation
      </div>
      <div className="mt-2 space-y-2">
        {sensoryRows.map((row) => (
          <label
            key={row.lab_test_type_id}
            className={`flex items-start gap-2 text-[12px] ${
              row.attested || !canAttest || isReleased ? "" : "cursor-pointer"
            }`}
          >
            <Checkbox
              checked={checkedIds.includes(row.lab_test_type_id)}
              disabled={row.attested || !canAttest || isReleased}
              onCheckedChange={() => toggleRow(row.lab_test_type_id, row.attested)}
              className="mt-0.5"
            />
            <span>
              <span className="font-medium text-slate-800">{row.name}</span>
              {row.spec_text && <span className="text-slate-500"> - {row.spec_text}</span>}
              {row.attested && <span className="ml-1.5 text-emerald-600">Attested</span>}
            </span>
          </label>
        ))}
      </div>
      {canAttest && !isReleased && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="mt-3 w-full"
          disabled={!hasUnsavedAttestations || attestSensory.isPending}
          onClick={handleConfirmAttestation}
        >
          {attestSensory.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Confirm Attestation
        </Button>
      )}
    </div>
  )
}

/** Green/amber/red release gate summary + sensory attest checklist. */
export function ReleaseGatePanel({ lotId, productId, isReleased }: ReleaseGatePanelProps) {
  const { data: gate, isLoading } = useReleaseGate(lotId, productId)
  const { user } = useAuthStore()
  const canAttest = user?.role === "admin" || user?.role === "qc_manager"

  if (isLoading) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-slate-200 bg-slate-50/50 py-6">
        <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
      </div>
    )
  }

  if (!gate) return null

  const isAllClear =
    gate.missing_tests.length === 0 &&
    gate.failing_tests.length === 0 &&
    gate.indeterminate_tests.length === 0 &&
    gate.sensory_all_attested

  // Remounts the checklist (resetting its local pending-checkbox state) whenever
  // the server's attested set changes.
  const attestedKey = gate.sensory_rows
    .filter((row) => row.attested)
    .map((row) => row.lab_test_type_id)
    .join(",")

  return (
    <div className="space-y-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
        Release Gate
      </h3>

      {gate.is_legacy_import && (
        <div className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-[12px] text-slate-600">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
          <span>Imported record - legacy test and sensory data are exempt from this gate.</span>
        </div>
      )}

      {isAllClear && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-2.5 text-[12px] font-medium text-emerald-700">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          All release gate checks passed
        </div>
      )}

      {(gate.missing_tests.length > 0 || gate.failing_tests.length > 0) && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <div className="flex items-center gap-1.5 text-[12px] font-semibold text-red-700">
            <AlertTriangle className="h-3.5 w-3.5" />
            Blocking Issues
          </div>
          <ul className="mt-1.5 space-y-1 text-[12px] text-red-700">
            {gate.missing_tests.map((name) => (
              <li key={`missing-${name}`}>Missing: {name}</li>
            ))}
            {gate.failing_tests.map((test) => (
              <li key={`failing-${test.name}`}>
                {test.name}: {test.result_value ?? "—"}
                {test.spec_text ? ` (spec: ${test.spec_text})` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {gate.indeterminate_tests.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="flex items-center gap-1.5 text-[12px] font-semibold text-amber-700">
            <AlertTriangle className="h-3.5 w-3.5" />
            Needs Attention (non-blocking)
          </div>
          <ul className="mt-1.5 space-y-1 text-[12px] text-amber-700">
            {gate.indeterminate_tests.map((test) => (
              <li key={`indeterminate-${test.name}`}>
                {test.name}: {test.result_value ?? "—"}
                {test.spec_text ? ` (spec: ${test.spec_text})` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {gate.sensory_rows.length > 0 && (
        <SensoryChecklist
          key={attestedKey}
          lotId={lotId}
          productId={productId}
          sensoryRows={gate.sensory_rows}
          canAttest={canAttest}
          isReleased={isReleased}
        />
      )}
    </div>
  )
}
