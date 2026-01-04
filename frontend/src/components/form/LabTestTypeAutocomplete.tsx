import React, { useState, useRef, useEffect, useMemo } from 'react'
import { useCombobox } from 'downshift'
import {
  useFloating,
  autoUpdate,
  offset,
  flip,
  shift,
  size,
  FloatingPortal,
  useMergeRefs,
} from '@floating-ui/react'
import { X } from 'lucide-react'
import type { LabTestType } from '@/types'

interface LabTestTypeAutocompleteProps {
  labTestTypes: LabTestType[]
  excludeIds?: number[]
  value: LabTestType | null
  onSelect: (labTest: LabTestType) => void
  onClear: () => void
  placeholder?: string
}

export function LabTestTypeAutocomplete({
  labTestTypes,
  excludeIds = [],
  value,
  onSelect,
  onClear,
  placeholder = 'Search tests...',
}: LabTestTypeAutocompleteProps) {
  const listRef = useRef<HTMLUListElement>(null)
  const [localInput, setLocalInput] = useState('')

  // Filter lab test types synchronously based on localInput
  const filteredLabTests = useMemo(() => {
    if (!localInput || localInput.length < 1) return []
    const searchLower = localInput.toLowerCase()
    return labTestTypes.filter((labTest) => {
      return (
        labTest.test_name.toLowerCase().includes(searchLower) ||
        labTest.test_category.toLowerCase().includes(searchLower)
      )
    })
  }, [localInput, labTestTypes])

  const {
    isOpen,
    getMenuProps,
    getInputProps,
    highlightedIndex,
    getItemProps,
    selectItem,
    closeMenu,
  } = useCombobox({
    items: filteredLabTests,
    inputValue: value ? value.test_name : localInput,
    itemToString: (item) => item?.test_name ?? '',
    onInputValueChange: ({ inputValue: newValue, type }) => {
      // Only update local input when not in selected mode
      if (!value && type === useCombobox.stateChangeTypes.InputChange) {
        setLocalInput(newValue || '')
      }
    },
    onSelectedItemChange: ({ selectedItem }) => {
      if (selectedItem && !excludeIds.includes(selectedItem.id)) {
        onSelect(selectedItem)
        setLocalInput('')
      }
    },
    stateReducer: (_state, actionAndChanges) => {
      const { changes, type } = actionAndChanges

      switch (type) {
        case useCombobox.stateChangeTypes.InputChange:
          return { ...changes, isOpen: !value }
        case useCombobox.stateChangeTypes.InputKeyDownEnter:
        case useCombobox.stateChangeTypes.ItemClick:
          return { ...changes, isOpen: false, highlightedIndex: -1 }
        default:
          return changes
      }
    },
  })

  const showDropdown = isOpen && !value && !!localInput && localInput.length >= 1

  // Floating UI for dropdown positioning
  const { refs, floatingStyles } = useFloating({
    open: showDropdown,
    placement: 'bottom-start',
    middleware: [
      offset(4),
      flip({ padding: 8 }),
      shift({ padding: 8 }),
      size({
        apply({ rects, elements }) {
          Object.assign(elements.floating.style, {
            minWidth: `${Math.max(rects.reference.width, 300)}px`,
          })
        },
        padding: 8,
      }),
    ],
    whileElementsMounted: autoUpdate,
  })

  const { ref: downshiftMenuRef, ...menuProps } = getMenuProps()
  const mergedMenuRef = useMergeRefs([
    refs.setFloating,
    downshiftMenuRef,
    listRef,
  ])

  // Clear local input when value is cleared externally
  useEffect(() => {
    if (!value) {
      setLocalInput('')
    }
  }, [value])

  // Scroll highlighted item into view
  useEffect(() => {
    if (isOpen && listRef.current && highlightedIndex >= 0) {
      const highlightedElement = listRef.current.children[highlightedIndex] as HTMLElement
      if (highlightedElement) {
        highlightedElement.scrollIntoView({ block: 'nearest' })
      }
    }
  }, [highlightedIndex, isOpen])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (value) {
      // When a value is selected, only allow clearing with Backspace/Delete
      if (e.key === 'Backspace' || e.key === 'Delete') {
        e.preventDefault()
        onClear()
      }
      return
    }

    if (e.key === 'Tab' || e.key === 'Enter') {
      if (isOpen && filteredLabTests.length > 0) {
        e.preventDefault()

        const itemToSelect = highlightedIndex >= 0
          ? filteredLabTests[highlightedIndex]
          : filteredLabTests.length === 1
            ? filteredLabTests[0]
            : null

        if (itemToSelect && !excludeIds.includes(itemToSelect.id)) {
          selectItem(itemToSelect)
          onSelect(itemToSelect)
        }

        closeMenu()
      } else if (e.key === 'Enter') {
        e.preventDefault()
      }
    } else if (e.key === 'Escape') {
      closeMenu()
    }
  }

  const handleClearClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClear()
  }

  const highlightMatch = (text: string, search: string) => {
    if (!search || search.length < 1) return text

    const regex = new RegExp(`(${search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
    const parts = text.split(regex)

    return (
      <>
        {parts.map((part, i) =>
          regex.test(part) ? (
            <strong key={i} className="font-semibold">{part}</strong>
          ) : (
            <span key={i}>{part}</span>
          )
        )}
      </>
    )
  }

  return (
    <div className="w-full">
      <div
        ref={refs.setReference}
        className="w-full flex items-center h-9 px-3 border border-slate-200 rounded-lg bg-white focus-within:ring-2 focus-within:ring-slate-900/10 focus-within:border-slate-300"
      >
        <input
          {...getInputProps({
            onKeyDown: handleKeyDown,
            disabled: !!value,
          })}
          placeholder={value ? '' : placeholder}
          className={`flex-1 h-full border-0 focus:outline-none focus:ring-0 bg-transparent placeholder:text-slate-400 text-sm ${
            value ? 'cursor-default' : ''
          }`}
          readOnly={!!value}
        />
        {value && (
          <button
            type="button"
            onClick={handleClearClick}
            className="ml-1 p-0.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <FloatingPortal>
        <ul
          ref={mergedMenuRef}
          {...menuProps}
          style={floatingStyles}
          className={`z-[9999] bg-white border border-slate-200 rounded-lg shadow-lg max-h-[280px] overflow-y-auto ${
            !showDropdown ? 'hidden' : ''
          }`}
        >
          {showDropdown && (
            filteredLabTests.length === 0 ? (
              <li className="px-4 py-3 text-sm text-slate-500">No tests found</li>
            ) : (
              filteredLabTests.map((labTest, index) => {
                const isExcluded = excludeIds.includes(labTest.id)
                return (
                  <li
                    key={labTest.id}
                    {...getItemProps({ item: labTest, index })}
                    className={`px-4 py-2.5 text-sm cursor-pointer transition-colors ${
                      isExcluded
                        ? 'opacity-50 cursor-not-allowed bg-slate-50'
                        : highlightedIndex === index
                        ? 'bg-slate-100'
                        : 'hover:bg-slate-50'
                    }`}
                    onClick={(e) => {
                      if (isExcluded) {
                        e.preventDefault()
                        e.stopPropagation()
                      }
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className={`font-medium ${isExcluded ? 'text-slate-400' : 'text-slate-900'}`}>
                          {highlightMatch(labTest.test_name, localInput)}
                        </p>
                        <p className={`text-xs mt-0.5 ${isExcluded ? 'text-slate-400' : 'text-slate-500'}`}>
                          {labTest.test_category}
                          {labTest.default_unit && ` - ${labTest.default_unit}`}
                        </p>
                      </div>
                      {isExcluded && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-200 text-slate-500 font-medium">
                          Added
                        </span>
                      )}
                    </div>
                  </li>
                )
              })
            )
          )}
        </ul>
      </FloatingPortal>
    </div>
  )
}
