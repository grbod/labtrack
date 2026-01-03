import React from 'react'

interface EditableCellProps {
  value: string
  isEditing: boolean
  type: 'text' | 'date'
  placeholder?: string
  onChange: (value: string) => void
  onStartEdit: () => void
  onEndEdit: () => void
  onTab?: () => void
}

export function EditableCell({
  value,
  isEditing,
  type,
  placeholder = 'Click to edit...',
  onChange,
  onStartEdit,
  onEndEdit,
  onTab,
}: EditableCellProps) {
  if (isEditing) {
    return (
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onEndEdit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            onEndEdit()
          } else if (e.key === 'Tab' && onTab) {
            e.preventDefault()
            onTab()
          }
        }}
        autoFocus
        className="w-full px-2 py-0.5 text-sm border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
    )
  }

  return (
    <div
      onClick={onStartEdit}
      className="px-2 py-0.5 cursor-pointer hover:bg-slate-50 rounded text-sm"
    >
      {value || <span className="text-slate-400 italic text-xs">{placeholder}</span>}
    </div>
  )
}
