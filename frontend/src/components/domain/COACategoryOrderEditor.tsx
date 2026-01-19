import { useState, useEffect } from "react"
import { toast } from "sonner"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, RotateCcw, Save, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  useCoaCategoryOrder,
  useUpdateCoaCategoryOrder,
  useResetCoaCategoryOrder,
  useActiveCategories,
} from "@/hooks/useCoaCategoryOrder"

interface SortableItemProps {
  id: string
  category: string
  getCategoryColor: (category: string) => string
}

function SortableItem({ id, category, getCategoryColor }: SortableItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-lg ${
        isDragging ? "shadow-lg opacity-90 z-10" : ""
      }`}
    >
      <button
        {...attributes}
        {...listeners}
        className="touch-none text-slate-400 hover:text-slate-600 cursor-grab active:cursor-grabbing"
      >
        <GripVertical className="h-5 w-5" />
      </button>
      <span
        className={`inline-flex items-center rounded-full px-3 py-1.5 text-[12px] font-semibold tracking-wide ${getCategoryColor(
          category
        )}`}
      >
        {category}
      </span>
    </div>
  )
}

export function COACategoryOrderEditor() {
  const { data: orderData, isLoading: isLoadingOrder } = useCoaCategoryOrder()
  const { data: activeCategories, isLoading: isLoadingCategories } = useActiveCategories()
  const updateMutation = useUpdateCoaCategoryOrder()
  const resetMutation = useResetCoaCategoryOrder()

  const [localOrder, setLocalOrder] = useState<string[]>([])
  const [hasChanges, setHasChanges] = useState(false)

  // Initialize local order from server data
  useEffect(() => {
    if (orderData?.category_order) {
      setLocalOrder(orderData.category_order)
    }
  }, [orderData])

  // Check for changes
  useEffect(() => {
    if (orderData?.category_order) {
      const changed =
        JSON.stringify(localOrder) !== JSON.stringify(orderData.category_order)
      setHasChanges(changed)
    }
  }, [localOrder, orderData])

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event

    if (over && active.id !== over.id) {
      setLocalOrder((items) => {
        const oldIndex = items.indexOf(active.id as string)
        const newIndex = items.indexOf(over.id as string)
        return arrayMove(items, oldIndex, newIndex)
      })
    }
  }

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({ category_order: localOrder })
      toast.success("Category order saved")
    } catch {
      toast.error("Failed to save category order")
    }
  }

  const handleReset = async () => {
    try {
      const result = await resetMutation.mutateAsync()
      setLocalOrder(result.category_order)
      toast.success("Category order reset to defaults")
    } catch {
      toast.error("Failed to reset category order")
    }
  }

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      Microbiological: "bg-emerald-100 text-emerald-700",
      "Heavy Metals": "bg-red-100 text-red-700",
      Pesticides: "bg-orange-100 text-orange-700",
      Nutritional: "bg-blue-100 text-blue-700",
      Physical: "bg-violet-100 text-violet-700",
      Chemical: "bg-amber-100 text-amber-700",
      Allergens: "bg-pink-100 text-pink-700",
      Organoleptic: "bg-teal-100 text-teal-700",
    }
    return colors[category] || "bg-slate-100 text-slate-600"
  }

  const isLoading = isLoadingOrder || isLoadingCategories
  const isMutating = updateMutation.isPending || resetMutation.isPending

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
      </div>
    )
  }

  // Merge configured order with any new active categories not yet in the order
  const displayCategories = [...localOrder]
  if (activeCategories) {
    for (const cat of activeCategories) {
      if (!displayCategories.includes(cat)) {
        displayCategories.push(cat)
      }
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[18px] font-bold text-slate-900">
            Test Category Display Order
          </h2>
          <p className="mt-1 text-[14px] text-slate-500">
            Drag and drop categories to set the order they appear in COAs. Tests
            are sorted alphabetically within each category.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleReset}
            disabled={isMutating}
            className="border-slate-200 h-10"
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            Reset to Default
          </Button>
          <Button
            onClick={handleSave}
            disabled={!hasChanges || isMutating}
            className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10"
          >
            {updateMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            <Save className="mr-2 h-4 w-4" />
            Save Order
          </Button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
        <p className="text-[13px] text-blue-700">
          Categories at the top will appear first in COAs. Categories not in
          this list will appear at the end, sorted alphabetically.
        </p>
      </div>

      {/* Sortable List */}
      <div className="space-y-2">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={displayCategories}
            strategy={verticalListSortingStrategy}
          >
            {displayCategories.map((category) => (
              <SortableItem
                key={category}
                id={category}
                category={category}
                getCategoryColor={getCategoryColor}
              />
            ))}
          </SortableContext>
        </DndContext>
      </div>

      {displayCategories.length === 0 && (
        <div className="text-center py-12 text-slate-500">
          <p>No categories found. Add lab test types to see categories here.</p>
        </div>
      )}
    </div>
  )
}
