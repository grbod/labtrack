import { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Lot, LotStatus } from "@/types"

/**
 * Animation configuration for Kanban cards
 * Enterprise-style: smooth fade + slide up, staggered cascade
 */
const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
      ease: [0.25, 0.1, 0.25, 1] as const, // Smooth easeOut (cubic bezier)
      delay: index * 0.05, // 50ms stagger between cards
    },
  }),
  exit: {
    opacity: 0,
    y: -20,
    transition: {
      duration: 0.2,
      ease: "easeIn" as const,
    },
  },
}

/**
 * Kanban column configuration with inline Tailwind classes.
 * Note: Classes are hardcoded to ensure Tailwind v4 detects them at build time.
 */
interface KanbanColumnConfig {
  id: LotStatus
  label: string
  headerBg: string
  headerText: string
  countBg: string
  countText: string
}

// Sample Tracker only shows active workflow columns
// Approved/released items appear in Release Queue, rejected in Archive
// NOTE: Drag-and-drop is DISABLED - status is auto-calculated based on test results
const KANBAN_COLUMNS: KanbanColumnConfig[] = [
  {
    id: "awaiting_results",
    label: "Awaiting Results",
    headerBg: "bg-sky-50",
    headerText: "text-sky-700",
    countBg: "bg-sky-100",
    countText: "text-sky-700",
  },
  {
    id: "partial_results",
    label: "Partial Results",
    headerBg: "bg-amber-50",
    headerText: "text-amber-700",
    countBg: "bg-amber-100",
    countText: "text-amber-700",
  },
  {
    id: "needs_attention",
    label: "Needs Attention",
    headerBg: "bg-red-50",
    headerText: "text-red-700",
    countBg: "bg-red-100",
    countText: "text-red-700",
  },
  {
    id: "under_review",
    label: "Under Review",
    headerBg: "bg-violet-50",
    headerText: "text-violet-700",
    countBg: "bg-violet-100",
    countText: "text-violet-700",
  },
]

const CARDS_PER_COLUMN = 8

interface KanbanBoardProps {
  lots: Lot[]
  onCardClick: (lot: Lot) => void
  staleWarningDays?: number
  staleCriticalDays?: number
  /** Reference number to highlight (from URL param after creating a sample) */
  highlightRef?: string | null
}

/**
 * Determines staleness level of a lot based on its age
 */
type StalenessLevel = "critical" | "warning" | "normal"

function calculateStaleness(
  lot: Lot,
  warningDays: number,
  criticalDays: number
): { level: StalenessLevel; daysOld: number } {
  // Append 'Z' to treat timestamp as UTC if not already present
  const timestamp = lot.created_at.endsWith("Z") ? lot.created_at : lot.created_at + "Z"
  const createdAt = new Date(timestamp)
  const now = new Date()
  const diffTime = now.getTime() - createdAt.getTime()
  const daysOld = Math.max(0, Math.floor(diffTime / (1000 * 60 * 60 * 24)))

  if (daysOld >= criticalDays) {
    return { level: "critical", daysOld }
  }
  if (daysOld >= warningDays) {
    return { level: "warning", daysOld }
  }
  return { level: "normal", daysOld }
}

/**
 * Formats lot type for display
 */
function formatLotType(lotType: string): string {
  return lotType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

/**
 * Individual Kanban card component
 */
interface KanbanCardProps {
  lot: Lot
  staleness: { level: StalenessLevel; daysOld: number }
  onClick: () => void
  index: number // For staggered animation
  isHighlighted?: boolean
}

function KanbanCardContent({ lot, staleness, onClick, isHighlighted }: Omit<KanbanCardProps, 'index'>) {
  const borderClass = {
    critical: "border-red-400 border-l-4",
    warning: "border-orange-400 border-l-4",
    normal: "border-slate-200",
  }[staleness.level]

  // Glow animation styles for highlighted cards
  const glowStyle = isHighlighted ? {
    animation: 'glow-fade 2s ease-in-out forwards',
  } : undefined

  // Get days badge configuration based on staleness
  const getDaysBadge = () => {
    const colorMap = {
      critical: "bg-red-100 text-red-700",
      warning: "bg-orange-100 text-orange-700",
      normal: "bg-slate-100 text-slate-600",
    }
    return { days: staleness.daysOld, color: colorMap[staleness.level] }
  }

  const daysBadge = getDaysBadge()

  // Get first product for display
  const product = lot.products?.[0] ?? null
  const hasMultipleProducts = (lot.products?.length ?? 0) > 1

  return (
    <div
      onClick={onClick}
      className={cn(
        "cursor-pointer rounded-lg border bg-white p-2.5 shadow-sm",
        "hover:border-slate-300 hover:shadow",
        borderClass
      )}
      style={glowStyle}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onClick()
        }
      }}
    >
      {/* Product info or lot type fallback */}
      {product ? (
        <>
          {/* Line 1: Brand + Days Badge */}
          <div className="flex items-start justify-between gap-2">
            <p className="text-[12px] font-semibold text-slate-900 truncate">
              {product.brand}
            </p>
            <span
              className={cn(
                "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[9px] font-semibold",
                daysBadge.color
              )}
            >
              {daysBadge.days}d
            </span>
          </div>
          {/* Line 2: Product Name */}
          <p className="text-[11px] text-slate-700 truncate">
            {product.product_name}
          </p>
          {/* Line 3: Flavor only (no size) */}
          {product.flavor && (
            <p className="text-[10px] text-slate-500 truncate">
              {product.flavor}
            </p>
          )}
          {/* Multi-product indicator */}
          {hasMultipleProducts && (
            <p className="text-[9px] text-blue-500 font-medium">
              +{lot.products!.length - 1} more product{lot.products!.length > 2 ? "s" : ""}
            </p>
          )}
        </>
      ) : (
        <div className="flex items-start justify-between gap-2">
          <p className="text-[12px] font-semibold text-slate-900 truncate">
            {formatLotType(lot.lot_type)}
          </p>
          <span
            className={cn(
              "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[9px] font-semibold",
              daysBadge.color
            )}
          >
            {daysBadge.days}d
          </span>
        </div>
      )}

      {/* Footer: Lab Ref + Badges */}
      <div className="mt-1.5 flex items-center justify-between">
        <p className="text-[11px] text-slate-600">
          Lab Ref <span className="font-mono font-medium">{lot.reference_number}</span>
        </p>
        <div className="flex items-center gap-1">
          {/* Retest Pending Badge */}
          {lot.has_pending_retest && (
            <span className="inline-flex items-center gap-0.5 rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-medium text-amber-700">
              <RefreshCw className="h-2.5 w-2.5" />
              Retest
            </span>
          )}
          {/* Tests Count Badge */}
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[9px] font-medium",
              (() => {
                const entered = lot.tests_entered ?? 0
                const total = lot.tests_total ?? 0
                const failed = lot.tests_failed ?? 0
                if (failed > 0) return "bg-red-100 text-red-700"
                if (total === 0) return "bg-slate-100 text-slate-500"
                // Darker green when user added extra tests (entered > required)
                if (entered > total && total > 0) return "bg-emerald-200 text-emerald-800"
                // Regular green when exactly matching required tests
                if (entered === total && total > 0) return "bg-emerald-100 text-emerald-700"
                if (entered > 0) return "bg-amber-100 text-amber-700"
                return "bg-slate-100 text-slate-500"
              })()
            )}
          >
            {lot.tests_entered ?? 0}/{lot.tests_total ?? 0}
          </span>
        </div>
      </div>
    </div>
  )
}

function KanbanCard({ lot, staleness, onClick, index, isHighlighted }: KanbanCardProps) {
  return (
    <motion.div
      variants={cardVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      custom={index}
      whileHover={{ scale: 1.01, transition: { duration: 0.15 } }}
      whileTap={{ scale: 0.98, transition: { duration: 0.1 } }}
    >
      <KanbanCardContent
        lot={lot}
        staleness={staleness}
        onClick={onClick}
        isHighlighted={isHighlighted}
      />
    </motion.div>
  )
}

/**
 * Individual Kanban column component
 */
interface KanbanColumnProps {
  config: KanbanColumnConfig
  lots: Array<Lot & { staleness: { level: StalenessLevel; daysOld: number } }>
  onCardClick: (lot: Lot) => void
  highlightRef?: string | null
}

function KanbanColumn({ config, lots, onCardClick, highlightRef }: KanbanColumnProps) {
  // Auto-expand if highlighted card would be hidden in collapsed view
  const highlightedIndex = highlightRef
    ? lots.findIndex(lot => lot.reference_number === highlightRef)
    : -1
  const shouldAutoExpand = highlightedIndex >= CARDS_PER_COLUMN

  const [isExpanded, setIsExpanded] = useState(shouldAutoExpand)

  const displayedLots = isExpanded ? lots : lots.slice(0, CARDS_PER_COLUMN)
  const hiddenCount = lots.length - CARDS_PER_COLUMN
  const showExpandButton = !isExpanded && hiddenCount > 0

  return (
    <div className="flex flex-col">
      {/* Column Header - colored by status */}
      <div className={cn(
        "mb-3 flex items-center justify-between rounded-lg px-3 py-2",
        config.headerBg
      )}>
        <h3 className={cn("text-[13px] font-semibold", config.headerText)}>
          {config.label}
        </h3>
        <span className={cn(
          "rounded-full px-2 py-0.5 text-[11px] font-semibold",
          config.countBg,
          config.countText
        )}>
          {lots.length}
        </span>
      </div>

      {/* Column Cards Container */}
      <motion.div
        layout
        className="flex-1 space-y-2 rounded-lg bg-slate-50/50 p-2 min-h-[200px]"
      >
        {lots.length === 0 ? (
          <p className="py-8 text-center text-[12px] text-slate-400">
            No samples
          </p>
        ) : (
          <>
            <AnimatePresence mode="popLayout">
              {displayedLots.map((lot, index) => (
                <KanbanCard
                  key={lot.id}
                  lot={lot}
                  staleness={lot.staleness}
                  onClick={() => onCardClick(lot)}
                  index={index}
                  isHighlighted={lot.reference_number === highlightRef}
                />
              ))}
            </AnimatePresence>
            <AnimatePresence mode="wait">
              {showExpandButton && (
                <motion.button
                  key="expand"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  onClick={() => setIsExpanded(true)}
                  className="w-full rounded-lg py-2 text-[12px] font-medium text-blue-600 hover:bg-blue-50 transition-colors"
                >
                  +{hiddenCount} more
                </motion.button>
              )}
              {isExpanded && lots.length > CARDS_PER_COLUMN && (
                <motion.button
                  key="collapse"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  onClick={() => setIsExpanded(false)}
                  className="w-full rounded-lg py-2 text-[12px] font-medium text-slate-500 hover:bg-slate-100 transition-colors"
                >
                  Show less
                </motion.button>
              )}
            </AnimatePresence>
          </>
        )}
      </motion.div>
    </div>
  )
}

/**
 * KanbanBoard displays lots organized by status in columns.
 *
 * Features:
 * - 4 columns: Awaiting Results, Partial Results, Needs Attention, Under Review
 * - Status is auto-calculated based on test results (no manual drag-and-drop)
 * - Approved/released items appear in Release Queue, rejected in Archive
 * - Stale items bubble to top with visual indicators (red/orange borders, warning icons)
 * - Maximum 8 cards per column with "+X more" button to expand
 * - Click cards to trigger onCardClick callback
 */
export function KanbanBoard({
  lots,
  onCardClick,
  staleWarningDays = 7,
  staleCriticalDays = 12,
  highlightRef,
}: KanbanBoardProps) {

  /**
   * Process and organize lots by column with staleness information
   */
  const columnData = useMemo(() => {
    // Group lots by status with staleness calculation
    const groupedLots: Record<
      string,
      Array<Lot & { staleness: { level: StalenessLevel; daysOld: number } }>
    > = {}

    // Initialize all columns
    KANBAN_COLUMNS.forEach((col) => {
      groupedLots[col.id] = []
    })

    lots.forEach((lot) => {
      const staleness = calculateStaleness(lot, staleWarningDays, staleCriticalDays)
      const lotWithStaleness = { ...lot, staleness }

      // Only include lots with statuses matching our 4 columns
      // Skip approved, released, rejected, awaiting_release - they appear elsewhere
      if (groupedLots[lot.status]) {
        groupedLots[lot.status].push(lotWithStaleness)
      }
    })

    // Sort each column: critical first, then warning, then normal
    // Within each staleness level, sort by age (oldest first)
    Object.keys(groupedLots).forEach((status) => {
      groupedLots[status].sort((a, b) => {
        const levelOrder = { critical: 0, warning: 1, normal: 2 }
        const levelDiff = levelOrder[a.staleness.level] - levelOrder[b.staleness.level]
        if (levelDiff !== 0) return levelDiff
        // Within same level, sort by age (older items first)
        return b.staleness.daysOld - a.staleness.daysOld
      })
    })

    return groupedLots
  }, [lots, staleWarningDays, staleCriticalDays])

  return (
    <div className="grid grid-cols-4 gap-4">
      {KANBAN_COLUMNS.map((column) => (
        <KanbanColumn
          key={column.id}
          config={column}
          lots={columnData[column.id] || []}
          onCardClick={onCardClick}
          highlightRef={highlightRef}
        />
      ))}
    </div>
  )
}
