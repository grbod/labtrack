import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { ClipboardList, Loader2 } from "lucide-react"

import { useLots } from "@/hooks/useLots"
import { useSystemSettings } from "@/hooks/useSettings"
import { KanbanBoard } from "@/components/domain/KanbanBoard"
import { SampleTable } from "@/components/domain/SampleTable"
import { SampleModal } from "@/components/domain/SampleModal"
import type { Lot } from "@/types"

export function SampleTrackerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const highlightRef = searchParams.get('highlight')

  // Clear highlight param from URL after animation completes (2s)
  useEffect(() => {
    if (highlightRef) {
      const timer = setTimeout(() => {
        setSearchParams({}, { replace: true })
      }, 2000)
      return () => clearTimeout(timer)
    }
  }, [highlightRef, setSearchParams])

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

  // After submission, navigate to next under_review sample or close
  const handleSubmitSuccess = () => {
    if (!selectedLot || !lotsData?.items) {
      handleCloseModal()
      return
    }

    // Find next under_review sample (excluding the one just submitted)
    const currentIndex = lotsData.items.findIndex(l => l.id === selectedLot.id)
    const items = lotsData.items

    // Look forward first, then wrap around
    for (let i = 1; i < items.length; i++) {
      const idx = (currentIndex + i) % items.length
      if (items[idx].status === "under_review") {
        setSelectedLot(items[idx])
        return
      }
    }

    // No more under_review samples - close modal
    handleCloseModal()
  }

  const handleNavigate = (direction: "prev" | "next") => {
    if (!selectedLot || !lotsData?.items || lotsData.items.length === 0) return
    const currentIndex = lotsData.items.findIndex(l => l.id === selectedLot.id)
    const totalItems = lotsData.items.length

    // Loop around when reaching ends
    if (direction === "prev") {
      const newIndex = currentIndex <= 0 ? totalItems - 1 : currentIndex - 1
      setSelectedLot(lotsData.items[newIndex])
    } else {
      const newIndex = currentIndex >= totalItems - 1 ? 0 : currentIndex + 1
      setSelectedLot(lotsData.items[newIndex])
    }
  }

  // Navigation is never disabled when looping (except if only 1 item)
  const hasMultipleItems = (lotsData?.items?.length ?? 0) > 1
  const prevDisabled = !hasMultipleItems
  const nextDisabled = !hasMultipleItems

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
            highlightRef={highlightRef}
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
        onSubmitSuccess={handleSubmitSuccess}
      />
      </div>
    </div>
  )
}
