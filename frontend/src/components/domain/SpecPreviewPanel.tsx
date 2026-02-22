import { useState, useEffect, useRef, useCallback } from "react"
import { AlertTriangle, ExternalLink, Check, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useProductTestSpecs } from "@/hooks/useProducts"
import type { Product, ProductTestSpecification } from "@/types"

const AUTO_DISMISS_MS = 5000

interface SpecPreviewPanelProps {
  product: Product | null
  onDismiss: () => void
  onChangeSpecs: (productId: number) => void
}

function groupByCategory(specs: ProductTestSpecification[]) {
  const groups: Record<string, ProductTestSpecification[]> = {}
  for (const spec of specs) {
    const cat = spec.test_category || "Other"
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(spec)
  }
  return groups
}

export function SpecPreviewPanel({ product, onDismiss, onChangeSpecs }: SpecPreviewPanelProps) {
  const [visible, setVisible] = useState(false)
  const hovering = useRef(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const remainingRef = useRef(AUTO_DISMISS_MS)
  const startTimeRef = useRef(0)
  const onDismissRef = useRef(onDismiss)
  onDismissRef.current = onDismiss

  const { data: specs, isLoading } = useProductTestSpecs(product?.id ?? 0)

  // Slide in when product changes
  useEffect(() => {
    if (product) {
      setVisible(true)
      remainingRef.current = AUTO_DISMISS_MS
    } else {
      setVisible(false)
    }
  }, [product])

  const dismiss = useCallback(() => {
    setVisible(false)
    // Wait for slide-out animation before unmounting
    setTimeout(() => onDismissRef.current(), 300)
  }, [])

  // Auto-dismiss timer
  useEffect(() => {
    if (!product || !visible) return

    function startTimer() {
      startTimeRef.current = Date.now()
      timerRef.current = setTimeout(dismiss, remainingRef.current)
    }

    if (!hovering.current) {
      startTimer()
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [product, visible, dismiss])

  const handleMouseEnter = () => {
    hovering.current = true
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
      // Save remaining time
      const elapsed = Date.now() - startTimeRef.current
      remainingRef.current = Math.max(0, remainingRef.current - elapsed)
    }
  }

  const handleMouseLeave = () => {
    hovering.current = false
    if (visible && product) {
      startTimeRef.current = Date.now()
      timerRef.current = setTimeout(dismiss, remainingRef.current)
    }
  }

  if (!product) return null

  const grouped = specs ? groupByCategory(specs) : {}
  const hasSpecs = specs && specs.length > 0

  return (
    <div
      className={`fixed bottom-4 right-4 z-50 max-w-sm w-[340px] rounded-lg shadow-lg border border-slate-200 bg-white transition-all duration-300 ease-in-out ${
        visible ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0 pointer-events-none"
      }`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Header */}
      <div className="px-3 py-2 border-b border-slate-100 bg-slate-50 rounded-t-lg">
        <p className="text-[12px] font-semibold text-slate-700 truncate">
          Test Specs: {product.display_name}
        </p>
      </div>

      {/* Body */}
      <div className="px-3 py-2 max-h-[280px] overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
            <span className="ml-2 text-[11px] text-slate-400">Loading specs...</span>
          </div>
        ) : !hasSpecs ? (
          <div className="flex flex-col items-center py-4 gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <p className="text-[12px] text-slate-600 text-center">No test specs configured for this product</p>
            <Button
              variant="outline"
              size="sm"
              className="text-[11px] h-7"
              onClick={() => onChangeSpecs(product.id)}
            >
              Set up specs <ExternalLink className="ml-1 h-3 w-3" />
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            {Object.entries(grouped).map(([category, categorySpecs]) => (
              <div key={category}>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">{category}</p>
                <div className="space-y-0.5">
                  {categorySpecs.map((spec) => (
                    <div key={spec.id} className="flex items-baseline justify-between gap-2 text-[11px]">
                      <span className="text-slate-600 truncate flex-1">{spec.test_name}</span>
                      <span className="text-slate-900 font-medium text-right shrink-0 max-w-[140px] truncate">{spec.specification}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-2 border-t border-slate-100 flex items-center justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          className="text-[11px] h-7"
          onClick={() => onChangeSpecs(product.id)}
        >
          Change Specs <ExternalLink className="ml-1 h-3 w-3" />
        </Button>
        <Button
          size="sm"
          className="text-[11px] h-7"
          onClick={() => {
            if (timerRef.current) clearTimeout(timerRef.current)
            dismiss()
          }}
        >
          <Check className="mr-1 h-3 w-3" /> Accept
        </Button>
      </div>
    </div>
  )
}
