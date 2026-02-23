import { useState, useRef, useEffect, useMemo } from "react"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { Check } from "lucide-react"
import { getInputTypeForSpec, POSITIVE_NEGATIVE_OPTIONS, getAutocompleteOptions } from "@/lib/spec-validation"

interface SmartResultInputProps {
  /** Current value */
  value: string
  /** Specification string (e.g., "< 10", "Negative") */
  specification: string
  /** Test unit (e.g., "Positive/Negative", "CFU/g") */
  testUnit: string | null
  /** Whether in editing mode */
  isEditing: boolean
  /** Whether input is disabled */
  disabled: boolean
  /** Callback to start editing */
  onStartEdit: () => void
  /** Callback when editing ends */
  onEndEdit: () => void
  /** Callback when value changes */
  onChange: (value: string) => void
  /** Callback for Tab navigation (isShiftTab: boolean) */
  onTab?: (isShiftTab: boolean) => void
  /** Callback for Enter navigation */
  onEnter?: () => void
  /** Callback to register input element for external focus management */
  onInputRef?: (el: HTMLInputElement | HTMLSelectElement | null) => void
  /** Additional class names */
  className?: string
}

/**
 * Smart input component that renders dropdown for P/N tests,
 * number input for numeric specs, or text input otherwise.
 */
export function SmartResultInput({
  value,
  specification,
  testUnit,
  isEditing,
  disabled,
  onStartEdit,
  onEndEdit,
  onChange,
  onTab,
  onEnter,
  onInputRef,
  className,
}: SmartResultInputProps) {
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null)
  const [localValue, setLocalValue] = useState(value)
  const [highlightedIndex, setHighlightedIndex] = useState(0)
  // Tracks when keyboard navigation already handled focus so blur should no-op
  const skipBlurRef = useRef(false)

  // Register input ref with parent when it changes
  useEffect(() => {
    if (isEditing && inputRef.current && onInputRef) {
      onInputRef(inputRef.current)
    }
    return () => {
      if (onInputRef) {
        onInputRef(null)
      }
    }
  }, [isEditing, onInputRef])

  const inputType = getInputTypeForSpec(specification, testUnit)

  // Sync local value with prop
  useEffect(() => {
    setLocalValue(value)
  }, [value])

  // Focus input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      if ('select' in inputRef.current) {
        inputRef.current.select()
      }
    }
  }, [isEditing])

  // Handle blur - save and end editing
  const handleBlur = () => {
    if (skipBlurRef.current) {
      skipBlurRef.current = false
      return
    }
    if (localValue !== value) {
      onChange(localValue)
    }
    onEndEdit()
  }

  // Handle key events
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setLocalValue(value) // Reset to original
      onEndEdit()
    } else if (e.key === 'Tab') {
      e.preventDefault()
      e.stopPropagation() // Prevent Radix Dialog focus trap from intercepting
      if (localValue !== value) {
        onChange(localValue)
      }
      skipBlurRef.current = true
      if (onTab) {
        onTab(e.shiftKey)
      } else {
        onEndEdit()
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (localValue !== value) {
        onChange(localValue)
      }
      if (onEnter) {
        onEnter()
      } else {
        onEndEdit()
      }
    }
  }

  // Disabled state - just show value
  if (disabled) {
    return (
      <span className={cn("text-sm text-slate-900", className)}>
        {value || '—'}
      </span>
    )
  }

  // Display mode - clickable to edit
  if (!isEditing) {
    return (
      <div
        onClick={onStartEdit}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onStartEdit()
          }
        }}
        tabIndex={0}
        className={cn(
          "min-h-[32px] px-2 py-1 rounded cursor-text flex items-center",
          "hover:bg-slate-50 transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-blue-50",
          className
        )}
      >
        {value ? (
          <span className="text-sm text-slate-900">{value}</span>
        ) : (
          <span className="text-sm text-slate-400 italic">Enter result</span>
        )}
      </div>
    )
  }

  // Get autocomplete options for this spec
  const autocompleteOptions = useMemo(
    () => getAutocompleteOptions(specification),
    [specification]
  )

  // Filter autocomplete options based on current input
  const filteredOptions = useMemo(() => {
    if (!localValue.trim()) return autocompleteOptions
    const search = localValue.trim().toLowerCase()
    return autocompleteOptions.filter(
      (opt) =>
        opt.value.toLowerCase().includes(search) ||
        opt.label.toLowerCase().includes(search)
    )
  }, [autocompleteOptions, localValue])

  // Reset highlighted index when filtered options change
  useEffect(() => {
    setHighlightedIndex(0)
  }, [filteredOptions.length])

  // Editing mode
  switch (inputType) {
    case 'dropdown':
      return (
        <select
          ref={inputRef as React.RefObject<HTMLSelectElement>}
          value={localValue}
          onChange={(e) => {
            setLocalValue(e.target.value)
            onChange(e.target.value)
          }}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          className={cn(
            "h-8 w-full px-2 text-sm border border-blue-500 rounded-md",
            "focus:outline-none focus:ring-2 focus:ring-blue-500",
            className
          )}
        >
          <option value="">Select...</option>
          {POSITIVE_NEGATIVE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )

    case 'autocomplete':
      return (
        <div className="relative">
          <Input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type="text"
            value={localValue}
            onChange={(e) => setLocalValue(e.target.value)}
            onBlur={() => {
              // Delay blur to allow click on options
              setTimeout(() => {
                if (skipBlurRef.current) {
                  skipBlurRef.current = false
                  return
                }
                if (localValue !== value) {
                  onChange(localValue)
                }
                onEndEdit()
              }, 150)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                // If dropdown is showing, just close it by resetting to original value
                // If dropdown is already closed, end editing (which closes modal via parent)
                setLocalValue(value)
                if (filteredOptions.length === 0) {
                  onEndEdit()
                }
              } else if (e.key === 'ArrowDown') {
                e.preventDefault()
                if (filteredOptions.length > 0) {
                  setHighlightedIndex(prev =>
                    prev < filteredOptions.length - 1 ? prev + 1 : 0
                  )
                }
              } else if (e.key === 'ArrowUp') {
                e.preventDefault()
                if (filteredOptions.length > 0) {
                  setHighlightedIndex(prev =>
                    prev > 0 ? prev - 1 : filteredOptions.length - 1
                  )
                }
              } else if (e.key === 'Tab') {
                e.preventDefault()
                e.stopPropagation()
                // Select highlighted option if available
                const finalValue = filteredOptions.length > 0
                  ? filteredOptions[highlightedIndex]?.value ?? localValue
                  : localValue
                if (finalValue !== value) {
                  onChange(finalValue)
                }
                skipBlurRef.current = true
                if (onTab) {
                  onTab(e.shiftKey)
                } else {
                  onEndEdit()
                }
              } else if (e.key === 'Enter') {
                e.preventDefault()
                // Select highlighted option if available
                const finalValue = filteredOptions.length > 0
                  ? filteredOptions[highlightedIndex]?.value ?? localValue
                  : localValue
                if (finalValue !== value) {
                  onChange(finalValue)
                }
                skipBlurRef.current = true
                if (onEnter) {
                  onEnter()
                } else if (onTab) {
                  onTab(false)
                } else {
                  skipBlurRef.current = false
                  onEndEdit()
                }
              }
            }}
            className={cn("h-8 text-sm border-blue-500 focus-visible:ring-blue-500", className)}
            placeholder="Type or select..."
          />
          {filteredOptions.length > 0 && (
            <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto">
              {filteredOptions.map((opt, index) => {
                const isHighlighted = index === highlightedIndex
                const isSelected = localValue.toLowerCase() === opt.value.toLowerCase()
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault()
                      setLocalValue(opt.value)
                      onChange(opt.value)
                      onEndEdit()
                    }}
                    className={cn(
                      "w-full px-3 py-1.5 text-left text-sm flex items-center justify-between",
                      isHighlighted ? "bg-blue-100" : isSelected ? "bg-blue-50" : "hover:bg-slate-50",
                      opt.passes ? "text-slate-900" : "text-slate-500"
                    )}
                  >
                    <span className="flex items-center gap-2">
                      {opt.label}
                      {opt.passes ? (
                        <span className="text-[10px] font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
                          PASS
                        </span>
                      ) : (
                        <span className="text-[10px] font-medium text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                          FAIL
                        </span>
                      )}
                    </span>
                    {isSelected && <Check className="h-3.5 w-3.5 text-blue-600" />}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )

    case 'number':
      {
        const prefixMatch = localValue.match(/^\s*([<>])\s*(.*)$/)
        // Auto-initialize prefix from spec when value is empty (e.g., spec "< 100" → default "<")
        const specPrefix = !localValue.trim() ? (specification.trim().match(/^([<>])/) ?? [])[1] || "" : ""
        const currentPrefix = prefixMatch ? prefixMatch[1] : specPrefix
        const numericPart = prefixMatch ? prefixMatch[2] : localValue

        return (
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              tabIndex={-1}
              className={cn(
                "h-8 w-7 shrink-0 rounded-l-md border border-r-0 text-xs font-mono",
                "hover:bg-slate-100 transition-colors",
                currentPrefix
                  ? "bg-blue-50 text-blue-700 border-blue-500"
                  : "bg-slate-50 text-slate-400 border-slate-200"
              )}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                const nextPrefix = currentPrefix === "<" ? ">" : currentPrefix === ">" ? "" : "<"
                const nextValue = nextPrefix ? `${nextPrefix}${numericPart}` : numericPart
                setLocalValue(nextValue)
                onChange(nextValue)
              }}
            >
              {currentPrefix || "="}
            </button>
            <Input
              ref={inputRef as React.RefObject<HTMLInputElement>}
              type="number"
              step="any"
              value={numericPart}
              onChange={(e) => {
                const nextValue = currentPrefix ? `${currentPrefix}${e.target.value}` : e.target.value
                setLocalValue(nextValue)
              }}
              onBlur={handleBlur}
              onKeyDown={handleKeyDown}
              className={cn(
                "h-8 text-sm border-blue-500 focus-visible:ring-blue-500 rounded-l-none",
                className
              )}
              placeholder="0"
            />
          </div>
        )
      }

    default:
      return (
        <Input
          ref={inputRef as React.RefObject<HTMLInputElement>}
          type="text"
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          className={cn("h-8 text-sm border-blue-500 focus-visible:ring-blue-500", className)}
          placeholder="Enter result"
        />
      )
  }
}
