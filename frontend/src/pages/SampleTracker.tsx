import { useState } from "react"
import { ClipboardList, Loader2 } from "lucide-react"

import { useLots } from "@/hooks/useLots"
import { useSystemSettings } from "@/hooks/useSettings"
import { KanbanBoard } from "@/components/domain/KanbanBoard"
import { SampleTable } from "@/components/domain/SampleTable"
import { SampleModal } from "@/components/domain/SampleModal"
import type { Lot } from "@/types"

export function SampleTrackerPage() {
  const [selectedLot, setSelectedLot] = useState<Lot | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Fetch lots for kanban (active workflow statuses only)
  // Exclude approved, released, awaiting_release, rejected - they appear in Release Queue/Archive
  const { data: lotsData, isLoading } = useLots({
    page_size: 100,
    exclude_statuses: ["approved", "released", "awaiting_release", "rejected"],
  })

  // Get stale thresholds from system settings
  const { settings: systemSettings } = useSystemSettings()

  const handleCardClick = (lot: Lot) => {
    setSelectedLot(lot)
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setSelectedLot(null)
  }

  const handleNavigate = (direction: "prev" | "next") => {
    if (!selectedLot || !lotsData?.items) return
    const currentIndex = lotsData.items.findIndex(l => l.id === selectedLot.id)

    // Stop at ends instead of wrapping
    if (direction === "prev" && currentIndex > 0) {
      setSelectedLot(lotsData.items[currentIndex - 1])
    } else if (direction === "next" && currentIndex < lotsData.items.length - 1) {
      setSelectedLot(lotsData.items[currentIndex + 1])
    }
  }

  // Calculate if navigation is disabled
  const currentIndex = selectedLot && lotsData?.items
    ? lotsData.items.findIndex(l => l.id === selectedLot.id)
    : -1
  const prevDisabled = currentIndex <= 0
  const nextDisabled = currentIndex < 0 || (lotsData?.items && currentIndex >= lotsData.items.length - 1)

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Sample Tracker</h1>
          <p className="mt-1.5 text-[15px] text-slate-500">
            Track your submitted samples through the workflow
          </p>
        </div>
      </div>

      {/* Kanban Board */}
      <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
          </div>
        ) : (
          <KanbanBoard
            lots={lotsData?.items || []}
            onCardClick={handleCardClick}
            staleWarningDays={systemSettings.staleWarningDays}
            staleCriticalDays={systemSettings.staleCriticalDays}
          />
        )}
      </div>

      {/* Table View Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-slate-600" />
          <h2 className="text-[15px] font-semibold text-slate-900">All Samples</h2>
        </div>

        {isLoading ? (
          <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
            </div>
          </div>
        ) : (
          <SampleTable
            lots={lotsData?.items || []}
            onRowClick={handleCardClick}
            staleWarningDays={systemSettings.staleWarningDays}
            staleCriticalDays={systemSettings.staleCriticalDays}
            pageSize={25}
          />
        )}
      </div>

      {/* Sample Modal */}
      <SampleModal
        lot={selectedLot}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        onNavigate={handleNavigate}
        prevDisabled={prevDisabled}
        nextDisabled={nextDisabled ?? false}
      />
      </div>
    </div>
  )
}
