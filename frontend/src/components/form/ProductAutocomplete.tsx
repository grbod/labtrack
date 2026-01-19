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
import type { Product } from '@/types'

interface ProductAutocompleteProps {
  value: {
    product_id: number | null
    product_name: string
  }
  products: Product[]
  isLoading?: boolean
  onSelect: (product: Product) => void
  onChange?: (text: string) => void
  onBlur?: () => void
  error?: boolean
  onNextCell?: () => void
  onPrevCell?: () => void
  /** Called when user presses Enter while "No products found" is showing */
  onNoProductsEnter?: () => void
}

export function ProductAutocomplete({
  value,
  products,
  isLoading = false,
  onSelect,
  onChange,
  onBlur,
  error = false,
  onNextCell,
  onPrevCell,
  onNoProductsEnter,
}: ProductAutocompleteProps) {
  const listRef = useRef<HTMLUListElement>(null)

  // Track current input for synchronous filtering
  const [localInput, setLocalInput] = useState(value.product_name)

  // Filter products synchronously based on localInput
  const filteredProducts = useMemo(() => {
    if (!localInput || localInput.length < 2) return []
    const searchLower = localInput.toLowerCase()
    return products.filter((product) => {
      return (
        product.brand.toLowerCase().includes(searchLower) ||
        product.product_name.toLowerCase().includes(searchLower) ||
        product.display_name.toLowerCase().includes(searchLower) ||
        (product.flavor && product.flavor.toLowerCase().includes(searchLower)) ||
        (product.size && product.size.toLowerCase().includes(searchLower))
      )
    })
  }, [localInput, products])

  const {
    isOpen,
    getMenuProps,
    getInputProps,
    highlightedIndex,
    getItemProps,
    selectItem,
    closeMenu,
  } = useCombobox({
    items: filteredProducts,
    inputValue: localInput,
    itemToString: (item) => item?.display_name ?? '',
    onInputValueChange: ({ inputValue: newValue, type }) => {
      setLocalInput(newValue || '')

      if (type === useCombobox.stateChangeTypes.InputChange) {
        if (onChange && newValue !== undefined) {
          onChange(newValue)
        }
      }
    },
    onSelectedItemChange: ({ selectedItem }) => {
      if (selectedItem) {
        onSelect(selectedItem)
      }
    },
    stateReducer: (_state, actionAndChanges) => {
      const { changes, type } = actionAndChanges

      switch (type) {
        case useCombobox.stateChangeTypes.InputChange:
          return { ...changes, isOpen: true }
        case useCombobox.stateChangeTypes.InputKeyDownEnter:
        case useCombobox.stateChangeTypes.ItemClick:
          return { ...changes, isOpen: false, highlightedIndex: -1 }
        default:
          return changes
      }
    },
  })

  const showDropdown = isOpen && !!localInput && localInput.length >= 2

  // Floating UI for dropdown positioning (escapes overflow containers)
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
            minWidth: `${Math.max(rects.reference.width, 400)}px`,
          })
        },
        padding: 8,
      }),
    ],
    whileElementsMounted: autoUpdate,
  })

  // Get menu props from Downshift (including its ref)
  const { ref: downshiftMenuRef, ...menuProps } = getMenuProps()

  // Merge all refs: Floating UI + Downshift + our listRef for scroll
  const mergedMenuRef = useMergeRefs([
    refs.setFloating,
    downshiftMenuRef,
    listRef,
  ])

  // Sync external value changes
  useEffect(() => {
    if (value.product_name !== localInput) {
      setLocalInput(value.product_name)
    }
  }, [value.product_name])

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
    if (e.key === 'Tab' || e.key === 'Enter') {
      if (isOpen && filteredProducts.length > 0) {
        e.preventDefault()

        const itemToSelect = highlightedIndex >= 0
          ? filteredProducts[highlightedIndex]
          : filteredProducts.length === 1
            ? filteredProducts[0]
            : null

        if (itemToSelect) {
          selectItem(itemToSelect)
          onSelect(itemToSelect)
        }

        closeMenu()

        // Handle navigation after selection
        if (e.key === 'Tab') {
          if (e.shiftKey && onPrevCell) {
            setTimeout(() => onPrevCell(), 10)
          } else if (!e.shiftKey && onNextCell) {
            setTimeout(() => onNextCell(), 10)
          }
        } else if (onNextCell) {
          // Enter key - move forward
          setTimeout(() => onNextCell(), 10)
        }
      } else if (e.key === 'Enter' && isOpen && filteredProducts.length === 0 && localInput.trim()) {
        // Enter pressed while "No products found" is showing
        e.preventDefault()
        if (onNoProductsEnter) {
          onNoProductsEnter()
        }
      } else if (e.key === 'Tab') {
        // Dropdown closed - handle Tab navigation
        if (e.shiftKey && onPrevCell) {
          e.preventDefault()
          onPrevCell()
        } else if (!e.shiftKey && onNextCell) {
          e.preventDefault()
          onNextCell()
        }
      } else if (e.key === 'Enter') {
        // Prevent form submission even when dropdown is closed
        e.preventDefault()
        if (onNextCell) {
          onNextCell()
        }
      }
    } else if (e.key === 'Escape') {
      closeMenu()
    }
  }

  const highlightMatch = (text: string, search: string) => {
    if (!search || search.length < 2) return text

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
        className={`w-full flex items-center ${error ? 'ring-2 ring-red-500 rounded bg-red-50' : ''}`}
      >
        <input
          {...getInputProps({ onKeyDown: handleKeyDown, onBlur })}
          placeholder="Type to search products..."
          className="w-full h-full border-0 focus:outline-none focus:ring-0 bg-transparent placeholder:text-slate-400"
        />
      </div>

      <FloatingPortal>
        <ul
          ref={mergedMenuRef}
          {...menuProps}
          style={floatingStyles}
          className={`z-[9999] bg-white border border-slate-200 rounded-md shadow-lg max-h-[320px] overflow-y-auto ${
            !showDropdown ? 'hidden' : ''
          }`}
        >
          {showDropdown && (
            isLoading ? (
              <li className="px-4 py-3 text-sm text-slate-500">Loading...</li>
            ) : filteredProducts.length === 0 ? (
              <li className="px-4 py-3 text-sm text-slate-500">
                No products found
                {onNoProductsEnter && (
                  <span className="block text-xs text-slate-400 mt-0.5">Press Enter to add new product</span>
                )}
              </li>
            ) : (
              filteredProducts.map((product, index) => (
                <li
                  key={product.id}
                  {...getItemProps({ item: product, index })}
                  className={`px-4 py-2 text-sm cursor-pointer transition-colors ${
                    highlightedIndex === index ? 'bg-slate-100' : 'hover:bg-slate-50'
                  }`}
                >
                  {highlightMatch(product.display_name, localInput)}
                </li>
              ))
            )
          )}
        </ul>
      </FloatingPortal>
    </div>
  )
}
