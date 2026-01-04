import { useState, useRef, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { getInputTypeForSpec, POSITIVE_NEGATIVE_OPTIONS } from "@/lib/spec-validation"

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
  className,
}: SmartResultInputProps) {
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null)
  const [localValue, setLocalValue] = useState(value)

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
      // Let the table handle tab navigation
      if (localValue !== value) {
        onChange(localValue)
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
            onEndEdit()
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

    case 'number':
      return (
        <Input
          ref={inputRef as React.RefObject<HTMLInputElement>}
          type="number"
          step="any"
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          className={cn("h-8 text-sm border-blue-500 focus-visible:ring-blue-500", className)}
          placeholder="0"
        />
      )

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
