import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Search, Loader2, CornerDownLeft } from "lucide-react"

import { useLotSearch } from "@/hooks/useLots"
import { Badge } from "@/components/ui/badge"
import { getStatusColor, getStatusLabel } from "@/lib/status-config"
import { cn } from "@/lib/utils"
import type { LotSearchResult } from "@/api/lots"

/** Where clicking a search hit takes the user, based on its workflow status. */
function destinationFor(hit: LotSearchResult): string {
  if (hit.status === "released") {
    return `/archive?search=${encodeURIComponent(hit.reference_number)}`
  }
  if (hit.status === "awaiting_release" && hit.primary_product_id != null) {
    return `/release/${hit.id}/${hit.primary_product_id}`
  }
  // Everything else lives on the Sample Tracker; deep-link + row highlight.
  return `/tracker?highlight=${encodeURIComponent(hit.reference_number)}`
}

/**
 * Global lot search shown in the top header on every page. Searches lots by
 * reference number, lot number, sublot number, and product name (server-side,
 * debounced). cmd/ctrl+k or "/" focuses it; arrows + Enter pick a result.
 */
export function GlobalSearch() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const [query, setQuery] = useState("")
  const [debounced, setDebounced] = useState("")
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)

  // Debounce the query (250ms) before it hits the network.
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 250)
    return () => clearTimeout(timer)
  }, [query])

  const { data, isFetching } = useLotSearch(debounced)
  const results = useMemo(() => data ?? [], [data])
  // Clamp the highlighted row so a shrinking result set never points out of
  // range (avoids a reset-in-effect); typing resets it to the top.
  const active = results.length > 0 ? Math.min(activeIndex, results.length - 1) : 0

  // cmd/ctrl+k, or "/" (when not already typing somewhere), focuses the box.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      const typing =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)

      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      } else if (e.key === "/" && !typing) {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [])

  // Close the dropdown on an outside click.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", onClick)
    return () => document.removeEventListener("mousedown", onClick)
  }, [open])

  const go = useCallback(
    (hit: LotSearchResult) => {
      setOpen(false)
      setQuery("")
      setDebounced("")
      inputRef.current?.blur()
      navigate(destinationFor(hit))
    },
    [navigate]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") {
        setOpen(false)
        inputRef.current?.blur()
        return
      }
      if (!open || results.length === 0) return
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setActiveIndex((i) => (i + 1) % results.length)
      } else if (e.key === "ArrowUp") {
        e.preventDefault()
        setActiveIndex((i) => (i - 1 + results.length) % results.length)
      } else if (e.key === "Enter") {
        e.preventDefault()
        const hit = results[active]
        if (hit) go(hit)
      }
    },
    [open, results, active, go]
  )

  const showDropdown = open && debounced.trim().length > 0

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActiveIndex(0)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search lots by reference, lot #, sublot, or product…"
          aria-label="Search lots"
          role="combobox"
          aria-expanded={showDropdown}
          aria-controls="global-search-results"
          className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50/70 pl-9 pr-9 text-sm text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:ring-2 focus:ring-slate-900/10"
        />
        <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 select-none rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-400 sm:inline-block">
          ⌘K
        </kbd>
      </div>

      {showDropdown && (
        <div
          id="global-search-results"
          role="listbox"
          className="absolute left-0 right-0 top-full z-50 mt-1.5 max-h-96 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {results.length === 0 ? (
            <div className="flex items-center gap-2 px-3 py-6 text-sm text-slate-500">
              {isFetching ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Searching…
                </>
              ) : (
                <span className="mx-auto">No lots match “{debounced.trim()}”.</span>
              )}
            </div>
          ) : (
            results.map((hit, index) => (
              <button
                key={`${hit.id}-${hit.primary_product_id ?? "x"}`}
                type="button"
                role="option"
                aria-selected={index === active}
                onMouseEnter={() => setActiveIndex(index)}
                onMouseDown={(e) => {
                  // Prevent the input's blur from closing the list before click.
                  e.preventDefault()
                  go(hit)
                }}
                className={cn(
                  "flex w-full items-center gap-3 px-3 py-2 text-left",
                  index === active ? "bg-slate-100" : "hover:bg-slate-50"
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-slate-900">
                      {hit.reference_number}
                    </span>
                    {hit.lot_number && hit.lot_number !== hit.reference_number && (
                      <span className="font-mono text-xs text-slate-500">
                        {hit.lot_number}
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 truncate text-xs text-slate-500">
                    {hit.product_label ?? "—"}
                    {hit.matched_sublot && (
                      <span className="ml-1.5 font-mono text-[11px] text-slate-400">
                        · sublot {hit.matched_sublot}
                      </span>
                    )}
                  </div>
                </div>
                <Badge variant={getStatusColor(hit.status)} className="shrink-0">
                  {getStatusLabel(hit.status)}
                </Badge>
                {index === active && (
                  <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
