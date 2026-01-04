"use client"

import * as React from "react"
import { ChevronDown } from "lucide-react"

import { cn } from "@/lib/utils"

export interface SelectOption {
  value: string
  label: string
}

interface SelectProps extends Omit<React.ComponentProps<"select">, "onChange"> {
  options: SelectOption[]
  placeholder?: string
  onChange?: (value: string) => void
}

function Select({
  className,
  options,
  placeholder,
  value,
  onChange,
  ...props
}: SelectProps) {
  return (
    <div className="relative">
      <select
        data-slot="select"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className={cn(
          "appearance-none w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 pr-8 text-sm shadow-xs transition-[color,box-shadow] outline-none",
          "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
          "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        {...props}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
    </div>
  )
}

export { Select }
