import { useState } from "react"
import { ChevronLeft, ChevronRight, ChevronDown, X, Package, Lock, Keyboard } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { getStatusLabel, getStatusBgClasses } from "@/lib/status-config"
import { useSublots } from "@/hooks/useLots"
import type { LotWithProductSpecs } from "@/types"

interface SampleModalHeaderProps {
  /** Lot with product specs */
  lot: LotWithProductSpecs
  /** Whether this lot is locked (approved/released) */
  isLocked: boolean
  /** Whether prev navigation is disabled */
  prevDisabled: boolean
  /** Whether next navigation is disabled */
  nextDisabled: boolean
  /** Callback to navigate to prev/next sample */
  onNavigate: (direction: "prev" | "next") => void
  /** Callback to close the modal */
  onClose: () => void
}

/**
 * Modal header with product display, navigation, and status.
 * Shows product name for single product, "MULTI-SKU" with collapsible list for multi-SKU.
 */
export function SampleModalHeader({
  lot,
  isLocked,
  prevDisabled,
  nextDisabled,
  onNavigate,
  onClose,
}: SampleModalHeaderProps) {
  const [isProductsExpanded, setIsProductsExpanded] = useState(true)

  const isMultiSku = lot.lot_type === "multi_sku_composite"
  const isParent = lot.lot_type === "parent_lot"
  const primaryProduct = lot.products[0]
  const { data: sublots = [] } = useSublots(lot.id, isParent)

  return (
    <DialogHeader className="flex-shrink-0 border-b border-slate-200 pb-4">
      <div className="flex items-center justify-between">
        {/* Left: Prev button */}
        <Button
          variant="ghost"
          size="icon"
          tabIndex={-1}
          onClick={() => onNavigate("prev")}
          disabled={prevDisabled}
          className="text-slate-400 hover:text-slate-600 disabled:opacity-30"
          aria-label="Previous sample"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>

        {/* Center: Title section */}
        <div className="flex-1 text-center px-4">
          {/* Main title */}
          <DialogTitle className="text-xl font-semibold text-slate-900">
            {isMultiSku ? (
              <span className="flex items-center justify-center gap-2">
                <Package className="h-5 w-5 text-slate-500" />
                MULTI-SKU
              </span>
            ) : primaryProduct ? (
              primaryProduct.display_name
            ) : (
              <span className="text-slate-400 italic">No product assigned</span>
            )}
          </DialogTitle>

          {/* Multi-SKU collapsible product list */}
          {isMultiSku && lot.products.length > 0 && (
            <Collapsible open={isProductsExpanded} onOpenChange={setIsProductsExpanded}>
              <CollapsibleTrigger className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mt-1 mx-auto">
                {lot.products.length} products
                <ChevronDown
                  className={cn(
                    "h-4 w-4 transition-transform duration-200",
                    isProductsExpanded && "rotate-180"
                  )}
                />
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2">
                <div className="space-y-1 text-sm text-slate-600">
                  {lot.products.map((product) => (
                    <div
                      key={product.id}
                      className="flex items-center justify-center gap-2"
                    >
                      <span>{product.display_name}</span>
                      {product.batch_number && (
                        <span className="font-mono text-xs text-slate-500">
                          {product.batch_number}
                        </span>
                      )}
                      {product.percentage && (
                        <span className="text-xs text-slate-400">
                          ({product.percentage}%)
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}

          {/* Sub-info: Lot number, Reference number, Status badge */}
          {/* Note: Using div instead of DialogDescription to avoid <p> containing <div> hydration error */}
          <div className="mt-2 flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono text-slate-600">{lot.lot_number}</span>
            <span className="text-slate-300">|</span>
            <span className="text-slate-600">{lot.reference_number}</span>
            <span className="text-slate-300">|</span>
            <Badge variant="outline" className={getStatusBgClasses(lot.status)}>
              {isLocked && <Lock className="h-3 w-3 mr-1" />}
              {getStatusLabel(lot.status)}
            </Badge>
          </div>

          {/* Parent-lot sublots: always-expanded, one per row */}
          {isParent && sublots.length > 0 && (
            <div className="mt-2">
              <p className="text-sm text-slate-500">Sublots ({sublots.length})</p>
              <div className="mt-1 space-y-1 text-sm text-slate-600">
                {sublots.map((s) => (
                  <div key={s.id} className="flex items-center justify-center gap-2">
                    <span className="font-mono">{s.sublot_number}</span>
                    {s.production_date && (
                      <span className="text-xs text-slate-400">{s.production_date}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Shortcuts + Next + Close buttons */}
        <div className="flex items-center gap-1">
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  tabIndex={-1}
                  className="text-slate-400 hover:text-slate-600 transition-colors p-2"
                  aria-label="Keyboard shortcuts"
                >
                  <Keyboard className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-[12px]">
                <div className="space-y-1">
                  <div className="font-medium text-slate-700 mb-1.5">Keyboard Shortcuts</div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Cycle operator</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">Shift + ↑↓</kbd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Next field</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">Tab</kbd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Save & next row</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">Enter</kbd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-slate-500">Cancel edit</span>
                    <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">Esc</kbd>
                  </div>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <Button
            variant="ghost"
            size="icon"
            tabIndex={-1}
            onClick={() => onNavigate("next")}
            disabled={nextDisabled}
            className="text-slate-400 hover:text-slate-600 disabled:opacity-30"
            aria-label="Next sample"
          >
            <ChevronRight className="h-5 w-5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            tabIndex={-1}
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </DialogHeader>
  )
}
