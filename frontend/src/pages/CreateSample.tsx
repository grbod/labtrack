import { useState, useCallback, useMemo, useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Loader2, Package, Beaker, X, CalendarDays, ArrowRight, Trash2 } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { AgGridReact } from "ag-grid-react"
import type { ColDef, ICellRendererParams, ValueFormatterParams } from "ag-grid-community"
import { useReactTable, getCoreRowModel, createColumnHelper, flexRender } from "@tanstack/react-table"
import type { ColumnDef } from "@tanstack/react-table"
import "ag-grid-community/styles/ag-grid.css"
import "ag-grid-community/styles/ag-theme-alpine.css"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ProductAutocomplete } from "@/components/form/ProductAutocomplete"

import { useProducts } from "@/hooks/useProducts"
import { useCreateLot, useLots, useCreateSublotsBulk } from "@/hooks/useLots"
import type { Product, LotType } from "@/types"

// User-selectable lot types (excludes sublot which is created automatically)
type SelectableLotType = "standard" | "parent_lot" | "multi_sku_composite"

const LOT_TYPES: { value: SelectableLotType; label: string; description: string }[] = [
  {
    value: "standard",
    label: "Standard Lot",
    description: "Single product, single lot",
  },
  {
    value: "parent_lot",
    label: "Parent Lot",
    description: "Master lot with sublots",
  },
  {
    value: "multi_sku_composite",
    label: "Multi-SKU Composite",
    description: "Multiple products combined",
  },
]

const sampleSchema = z.object({
  lot_number: z.string().min(1, "Lot number is required"),
  lot_type: z.enum(["standard", "parent_lot", "multi_sku_composite"]),
  mfg_date: z.string().optional(),
  exp_date: z.string().optional(),
  reference_number: z.string().optional(),
  generate_coa: z.boolean(),
})

type SampleForm = z.infer<typeof sampleSchema>

interface SelectedProduct {
  product: Product
  percentage?: number
}

// Types for AG-Grid rows
interface SubBatchRow {
  id: number
  mfg_date: string
  batch_number: string
}

interface CompositeProductRow {
  id: number
  product_id: number | null
  product_name: string
  mfg_date: string
  batch_number: string
}

export function CreateSamplePage() {
  const navigate = useNavigate()
  const [isProductDialogOpen, setIsProductDialogOpen] = useState(false)
  const [selectedProducts, setSelectedProducts] = useState<SelectedProduct[]>([])
  const [productSearch, setProductSearch] = useState("")

  // Sub-batch state for parent_lot
  const [subBatches, setSubBatches] = useState<SubBatchRow[]>([
    { id: 1, mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }
  ])
  const [nextSubBatchId, setNextSubBatchId] = useState(2)

  // Composite products state for multi_sku_composite
  const [compositeProducts, setCompositeProducts] = useState<CompositeProductRow[]>([
    { id: 1, product_id: null, product_name: '', mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }
  ])
  const [nextCompositeId, setNextCompositeId] = useState(2)
  const [editingCompositeCell, setEditingCompositeCell] = useState<{ rowId: number; columnId: string } | null>(null)

  const { data: productsData, isLoading: isProductsLoading } = useProducts({ page_size: 100 })
  const { data: lotsData } = useLots({ page: 1, page_size: 10 })
  const createMutation = useCreateLot()
  const createSublotsMutation = useCreateSublotsBulk()

  const form = useForm<SampleForm>({
    resolver: zodResolver(sampleSchema),
    defaultValues: {
      lot_type: "standard",
      generate_coa: true,
    },
  })

  const { register, handleSubmit, watch, setValue, formState: { errors } } = form
  const watchedLotType = watch("lot_type")
  const watchedMfgDate = watch("mfg_date")

  // Helper to calculate expiry date from mfg_date and expiry_duration_months
  const calculateExpiryDate = useCallback((mfgDate: string, expiryMonths: number): string => {
    const date = new Date(mfgDate)
    date.setMonth(date.getMonth() + expiryMonths)
    return date.toISOString().split('T')[0]
  }, [])

  // Auto-calculate exp_date when mfg_date or product changes
  useEffect(() => {
    if (!watchedMfgDate) {
      setValue("exp_date", "")
      return
    }

    // For STANDARD and parent_lot, use selectedProducts[0]
    // For multi_sku_composite, use shortest expiry from compositeProducts
    if (watchedLotType === "multi_sku_composite") {
      const validProducts = compositeProducts.filter(cp => cp.product_id !== null)
      if (validProducts.length > 0 && productsData?.items) {
        // Find shortest expiry duration among selected products
        const minExpiry = validProducts.reduce((min, cp) => {
          const product = productsData.items.find(p => p.id === cp.product_id)
          return product ? Math.min(min, product.expiry_duration_months) : min
        }, Infinity)
        if (minExpiry !== Infinity) {
          setValue("exp_date", calculateExpiryDate(watchedMfgDate, minExpiry))
        }
      }
    } else {
      // STANDARD or parent_lot
      if (selectedProducts.length > 0) {
        const expiryMonths = selectedProducts[0].product.expiry_duration_months
        setValue("exp_date", calculateExpiryDate(watchedMfgDate, expiryMonths))
      }
    }
  }, [watchedMfgDate, selectedProducts, compositeProducts, watchedLotType, productsData, setValue, calculateExpiryDate])

  const onSubmit = async (formData: SampleForm) => {
    console.log('=== onSubmit called ===', formData)
    try {
      if (formData.lot_type === "parent_lot") {
        // For parent_lot: Create lot then create sublots
        const validSubBatches = subBatches.filter(sb => sb.batch_number.trim() !== '')
        if (validSubBatches.length === 0) {
          alert("Please add at least one sub-batch")
          return
        }

        // Calculate earliest mfg date from sub-batches
        const earliestMfgDate = validSubBatches.reduce((min, sb) =>
          sb.mfg_date < min ? sb.mfg_date : min, validSubBatches[0].mfg_date)

        // Calculate exp_date from earliest mfg_date + product expiry
        const productExpiry = selectedProducts[0]?.product.expiry_duration_months || 36
        const calculatedExpDate = calculateExpiryDate(earliestMfgDate, productExpiry)

        const lot = await createMutation.mutateAsync({
          lot_number: formData.lot_number,
          lot_type: "parent_lot" as LotType,
          mfg_date: earliestMfgDate,
          exp_date: calculatedExpDate,
          reference_number: formData.reference_number || undefined,
          generate_coa: formData.generate_coa,
          products: selectedProducts.map((sp) => ({
            product_id: sp.product.id,
            percentage: sp.percentage,
          })),
        })

        // Create sublots
        await createSublotsMutation.mutateAsync({
          lotId: lot.id,
          sublots: validSubBatches.map(sb => ({
            sublot_number: `${formData.lot_number}-${sb.batch_number}`,
            production_date: sb.mfg_date,
          })),
        })

        navigate("/")
      } else if (formData.lot_type === "multi_sku_composite") {
        // For multi_sku_composite: Use composite products grid data

        // Check if there are any rows
        if (compositeProducts.length === 0) {
          alert("Please add at least one product row")
          return
        }

        // Check for products without valid product_id
        const invalidProducts = compositeProducts.filter(cp => cp.product_id === null)
        if (invalidProducts.length > 0) {
          alert("Please select valid products from the database for all rows. Hover over invalid entries to see the error.")
          return
        }

        // Check for products without batch numbers
        const productsWithoutBatch = compositeProducts.filter(cp => cp.batch_number.trim() === '')
        if (productsWithoutBatch.length > 0) {
          alert("Please enter batch numbers for all products")
          return
        }

        const validProducts = compositeProducts.filter(cp => cp.product_id !== null && cp.batch_number.trim() !== '')

        // Generate composite lot number from batch numbers
        const compositeLotNumber = "COMP-" + validProducts.map(p => p.batch_number).join("-")

        // Calculate equal percentages for all products
        const equalPercentage = 100 / validProducts.length

        // Calculate earliest mfg date
        const earliestMfgDate = validProducts.reduce((min, cp) =>
          cp.mfg_date < min ? cp.mfg_date : min, validProducts[0].mfg_date)

        // Calculate exp_date using shortest expiry among products
        const minExpiry = validProducts.reduce((min, cp) => {
          const product = productsData?.items.find(p => p.id === cp.product_id)
          return product ? Math.min(min, product.expiry_duration_months) : min
        }, Infinity)
        const calculatedExpDate = minExpiry !== Infinity
          ? calculateExpiryDate(earliestMfgDate, minExpiry)
          : undefined

        await createMutation.mutateAsync({
          lot_number: compositeLotNumber,
          lot_type: "multi_sku_composite" as LotType,
          mfg_date: earliestMfgDate,
          exp_date: calculatedExpDate,
          reference_number: formData.reference_number || undefined,
          generate_coa: formData.generate_coa,
          products: validProducts.map((cp) => ({
            product_id: cp.product_id!,
            percentage: equalPercentage,
          })),
        })

        navigate("/")
      } else {
        // STANDARD lot - use original logic
        const payload = {
          lot_number: formData.lot_number,
          lot_type: formData.lot_type as LotType,
          mfg_date: formData.mfg_date || undefined,
          exp_date: formData.exp_date || undefined,
          reference_number: formData.reference_number || undefined,
          generate_coa: formData.generate_coa,
          products: selectedProducts.map((sp) => ({
            product_id: sp.product.id,
            percentage: sp.percentage,
          })),
        }
        console.log('=== STANDARD lot payload ===', JSON.stringify(payload, null, 2))
        await createMutation.mutateAsync(payload)
        console.log('=== Mutation succeeded, navigating ===')
        navigate("/")
      }
    } catch (error: any) {
      console.error('=== Submit error ===', error)
      // Log the actual validation error from the backend
      if (error?.response?.data) {
        console.error('=== Backend validation error ===', JSON.stringify(error.response.data, null, 2))
      }
      if (error?.response?.data?.detail) {
        // FastAPI validation errors
        alert(`Validation error: ${JSON.stringify(error.response.data.detail)}`)
      }
    }
  }

  const addProduct = (product: Product) => {
    if (!selectedProducts.find((sp) => sp.product.id === product.id)) {
      setSelectedProducts([...selectedProducts, { product }])
    }
    setIsProductDialogOpen(false)
    setProductSearch("")
  }

  const removeProduct = (productId: number) => {
    setSelectedProducts(selectedProducts.filter((sp) => sp.product.id !== productId))
  }

  const filteredProducts = productsData?.items.filter(
    (p) =>
      p.display_name.toLowerCase().includes(productSearch.toLowerCase()) ||
      p.brand.toLowerCase().includes(productSearch.toLowerCase())
  )

  // Sub-batch grid handlers
  const addSubBatch = useCallback(() => {
    setSubBatches(prev => [
      ...prev,
      { id: nextSubBatchId, mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }
    ])
    setNextSubBatchId(prev => prev + 1)
  }, [nextSubBatchId])

  const removeSubBatch = useCallback((id: number) => {
    setSubBatches(prev => prev.filter(sb => sb.id !== id))
  }, [])

  const subBatchColDefs = useMemo<ColDef<SubBatchRow>[]>(() => [
    {
      field: 'mfg_date',
      headerName: 'Mfg Date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      flex: 1,
    },
    {
      field: 'batch_number',
      headerName: 'Batch #',
      editable: true,
      flex: 1,
    },
    {
      headerName: '',
      width: 60,
      cellRenderer: (params: ICellRendererParams<SubBatchRow>) => (
        <button
          onClick={() => removeSubBatch(params.data?.id ?? 0)}
          className="p-1 text-slate-400 hover:text-red-600 transition-colors"
          type="button"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      ),
    },
  ], [removeSubBatch])

  // Composite products grid handlers
  const addCompositeProduct = useCallback(() => {
    setCompositeProducts(prev => [
      ...prev,
      { id: nextCompositeId, product_id: null, product_name: '', mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }
    ])
    setNextCompositeId(prev => prev + 1)
  }, [nextCompositeId])

  const removeCompositeProduct = useCallback((id: number) => {
    setCompositeProducts(prev => prev.filter(cp => cp.id !== id))
  }, [])

  const productOptions = useMemo(() =>
    productsData?.items.map(p => p.display_name) || [],
    [productsData]
  )

  // TanStack Table columns for Composite Products
  const compositeColumnHelper = createColumnHelper<CompositeProductRow>()
  const compositeColumns = useMemo<ColumnDef<CompositeProductRow>[]>(() => [
    compositeColumnHelper.accessor('product_name', {
      header: 'Product',
      cell: (info) => {
        const rowId = info.row.original.id
        const currentProduct = info.row.original

        return (
          <ProductAutocomplete
            value={currentProduct}
            products={productsData?.items || []}
            isLoading={isProductsLoading}
            onSelect={(product) => {
              setCompositeProducts(prev =>
                prev.map(cp => cp.id === rowId
                  ? { ...cp, product_id: product.id, product_name: product.display_name }
                  : cp
                )
              )
            }}
            onChange={(text) => {
              // Clear product_id when user starts typing (always editable)
              setCompositeProducts(prev =>
                prev.map(cp => cp.id === rowId
                  ? { ...cp, product_id: null, product_name: text }
                  : cp
                )
              )
            }}
            error={!currentProduct.product_id && currentProduct.product_name.trim() !== ''}
            onNextCell={() => {
              // Move to mfg_date column
              setEditingCompositeCell({ rowId, columnId: 'mfg_date' })
            }}
          />
        )
      },
    }),
    compositeColumnHelper.accessor('mfg_date', {
      header: 'Mfg Date',
      cell: (info) => {
        const rowId = info.row.original.id
        const isEditing = editingCompositeCell?.rowId === rowId && editingCompositeCell?.columnId === 'mfg_date'

        if (isEditing) {
          return (
            <input
              type="date"
              value={info.getValue()}
              onChange={(e) => {
                setCompositeProducts(prev =>
                  prev.map(cp => cp.id === rowId ? { ...cp, mfg_date: e.target.value } : cp)
                )
              }}
              onBlur={() => setEditingCompositeCell(null)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  setEditingCompositeCell(null)
                } else if (e.key === 'Tab') {
                  e.preventDefault()
                  // Move to batch_number column
                  setEditingCompositeCell({ rowId, columnId: 'batch_number' })
                }
              }}
              autoFocus
              className="w-full px-2 py-0.5 text-sm border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          )
        }

        return (
          <div
            onClick={() => setEditingCompositeCell({ rowId, columnId: 'mfg_date' })}
            className="px-2 py-0.5 cursor-pointer hover:bg-slate-50 rounded text-sm"
          >
            {info.getValue()}
          </div>
        )
      },
    }),
    compositeColumnHelper.accessor('batch_number', {
      header: 'Batch #',
      cell: (info) => {
        const rowId = info.row.original.id
        const isEditing = editingCompositeCell?.rowId === rowId && editingCompositeCell?.columnId === 'batch_number'

        if (isEditing) {
          return (
            <input
              type="text"
              value={info.getValue()}
              onChange={(e) => {
                setCompositeProducts(prev =>
                  prev.map(cp => cp.id === rowId ? { ...cp, batch_number: e.target.value } : cp)
                )
              }}
              onBlur={() => setEditingCompositeCell(null)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  setEditingCompositeCell(null)
                } else if (e.key === 'Tab') {
                  // Close editing
                  setEditingCompositeCell(null)

                  // Check if we're on the last row
                  const currentRowIndex = compositeProducts.findIndex(cp => cp.id === rowId)
                  if (currentRowIndex === compositeProducts.length - 1) {
                    // Add new row immediately so Tab can find it
                    const newRow = {
                      id: nextCompositeId,
                      product_id: null,
                      product_name: '',
                      mfg_date: new Date().toISOString().split('T')[0],
                      batch_number: ''
                    }
                    setCompositeProducts(prev => [...prev, newRow])
                    setNextCompositeId(prev => prev + 1)
                  }
                  // Don't preventDefault - let Tab naturally move to next row's Product input
                }
              }}
              autoFocus
              className="w-full px-2 py-0.5 text-sm border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          )
        }

        return (
          <div
            onClick={() => setEditingCompositeCell({ rowId, columnId: 'batch_number' })}
            className="px-2 py-0.5 cursor-pointer hover:bg-slate-50 rounded text-sm"
          >
            {info.getValue() || <span className="text-slate-400 italic text-xs">Click to edit...</span>}
          </div>
        )
      },
    }),
    compositeColumnHelper.display({
      id: 'actions',
      header: '',
      cell: (info) => (
        <button
          onClick={() => removeCompositeProduct(info.row.original.id)}
          className="text-slate-400 hover:text-red-600 transition-colors p-1"
          type="button"
          title="Delete row"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      ),
      size: 40,
    }),
  ], [editingCompositeCell, productsData, removeCompositeProduct])

  // TanStack Table instance for Composite Products
  const compositeTable = useReactTable({
    data: compositeProducts,
    columns: compositeColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id.toString(),
  })

  const defaultColDef = useMemo<ColDef>(() => ({
    resizable: true,
    sortable: false,
  }), [])

  return (
    <div className="space-y-8 max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Create Sample</h1>
        <p className="mt-1.5 text-[15px] text-slate-500">
          Submit a new lot for lab testing
        </p>
      </div>

      {/* Recent Lots Summary */}
      {lotsData && lotsData.items.length > 0 && (
        <div className="rounded-xl border border-slate-200/60 bg-white px-6 py-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
          <p className="text-[13px] font-semibold text-slate-500 mb-3">Recent Submissions</p>
          <div className="flex gap-2 flex-wrap">
            {lotsData.items.slice(0, 5).map((lot) => (
              <span
                key={lot.id}
                className="px-3 py-1.5 bg-slate-100 rounded-lg text-[12px] font-mono font-semibold text-slate-700 tracking-wide"
              >
                {lot.reference_number}
              </span>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Lot Type Selection */}
        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
          <div className="border-b border-slate-100 px-6 py-4">
            <div className="flex items-center gap-2">
              <Package className="h-5 w-5 text-slate-600" />
              <h2 className="font-semibold text-slate-900 text-[15px]">Lot Type</h2>
            </div>
            <p className="mt-1 text-[13px] text-slate-500">
              Select the type of lot you're creating
            </p>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {LOT_TYPES.map((type) => (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setValue("lot_type", type.value)}
                  className={`p-4 border-2 rounded-xl text-left transition-all duration-200 ${
                    watchedLotType === type.value
                      ? "border-slate-900 bg-slate-50 shadow-sm"
                      : "border-slate-200/80 hover:border-slate-300 hover:bg-slate-50/50"
                  }`}
                >
                  <p className="font-semibold text-slate-900 text-[14px]">{type.label}</p>
                  <p className="text-[12px] text-slate-500 mt-1">
                    {type.description}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* STANDARD: Product Selection - BEFORE Lot Details */}
        {watchedLotType === "standard" && (
          <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
            <div className="border-b border-slate-100 px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900 text-[15px]">Product</h2>
                  <p className="mt-1 text-[13px] text-slate-500">
                    Select the product for this lot
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsProductDialogOpen(true)}
                  className="border-slate-200 h-9"
                  disabled={selectedProducts.length > 0}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Select Product
                </Button>
              </div>
            </div>
            <div className="p-6">
              {selectedProducts.length === 0 ? (
                <div className="text-center py-6">
                  <div className="w-12 h-12 mx-auto rounded-xl bg-slate-100 flex items-center justify-center">
                    <Package className="h-6 w-6 text-slate-400" />
                  </div>
                  <p className="mt-3 text-[14px] text-slate-500">No product selected</p>
                  <button
                    type="button"
                    onClick={() => setIsProductDialogOpen(true)}
                    className="mt-2 text-[13px] font-semibold text-blue-600 hover:text-blue-700"
                  >
                    Select a product
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-3 p-4 border border-slate-200/80 rounded-xl bg-slate-50/30">
                  <div className="flex-1">
                    <p className="font-semibold text-slate-900 text-[14px]">{selectedProducts[0].product.display_name}</p>
                    <p className="text-[12px] text-slate-500 mt-0.5">
                      {selectedProducts[0].product.brand} • Expires {selectedProducts[0].product.expiry_duration_months} months from mfg
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeProduct(selectedProducts[0].product.id)}
                    className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Lot Details */}
        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
          <div className="border-b border-slate-100 px-6 py-4">
            <div className="flex items-center gap-2">
              <Beaker className="h-5 w-5 text-slate-600" />
              <h2 className="font-semibold text-slate-900 text-[15px]">Lot Details</h2>
            </div>
          </div>
          <div className="p-6 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="lot_number" className="text-[13px] font-semibold text-slate-700">Lot Number *</Label>
                <Input
                  id="lot_number"
                  {...register("lot_number")}
                  placeholder="e.g., ABC123"
                  aria-invalid={!!errors.lot_number}
                  className="border-slate-200 h-10"
                />
                {errors.lot_number && (
                  <p className="text-[13px] text-red-600">{errors.lot_number.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="reference_number" className="text-[13px] font-semibold text-slate-700">Reference Number</Label>
                <Input
                  id="reference_number"
                  {...register("reference_number")}
                  placeholder="Auto-generated if empty"
                  className="border-slate-200 h-10"
                />
                <p className="text-[11px] text-slate-500">
                  Leave blank to auto-generate (YYMMDD-XXX)
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="mfg_date" className="flex items-center gap-2 text-[13px] font-semibold text-slate-700">
                  <CalendarDays className="h-4 w-4" />
                  Manufacturing Date
                </Label>
                <Input
                  id="mfg_date"
                  type="date"
                  {...register("mfg_date")}
                  className="border-slate-200 h-10"
                  onKeyDown={(e) => {
                    if (e.key === 't' || e.key === 'T') {
                      e.preventDefault()
                      setValue("mfg_date", new Date().toISOString().split('T')[0])
                    }
                  }}
                />
                <p className="text-[11px] text-slate-500">
                  Press "T" for today's date
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="exp_date" className="flex items-center gap-2 text-[13px] font-semibold text-slate-700">
                  <CalendarDays className="h-4 w-4" />
                  Expiration Date
                </Label>
                <Input
                  id="exp_date"
                  type="date"
                  {...register("exp_date")}
                  className="border-slate-200 h-10 bg-slate-50"
                  readOnly
                />
                <p className="text-[11px] text-slate-500">
                  Auto-calculated from product expiry
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5 pt-2">
              <input
                id="generate_coa"
                type="checkbox"
                {...register("generate_coa")}
                className="rounded border-slate-300 text-slate-900 focus:ring-slate-500 h-4 w-4"
              />
              <Label htmlFor="generate_coa" className="font-normal text-[14px] text-slate-700">
                Generate COA when approved
              </Label>
            </div>
          </div>
        </div>

        {/* parent_lot: Sub-Batches Grid */}
        {watchedLotType === "parent_lot" && (
          <>
            {/* Single Product Selection for Parent Lot */}
            <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
              <div className="border-b border-slate-100 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold text-slate-900 text-[15px]">Product</h2>
                    <p className="mt-1 text-[13px] text-slate-500">
                      Select the product for this master lot (all sub-batches will use this product)
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setIsProductDialogOpen(true)}
                    className="border-slate-200 h-9"
                    disabled={selectedProducts.length > 0}
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Select Product
                  </Button>
                </div>
              </div>
              <div className="p-6">
                {selectedProducts.length === 0 ? (
                  <div className="text-center py-6">
                    <p className="text-[14px] text-slate-500">No product selected</p>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 p-4 border border-slate-200/80 rounded-xl bg-slate-50/30">
                    <div className="flex-1">
                      <p className="font-semibold text-slate-900 text-[14px]">{selectedProducts[0].product.display_name}</p>
                      <p className="text-[12px] text-slate-500 mt-0.5">{selectedProducts[0].product.brand}</p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removeProduct(selectedProducts[0].product.id)}
                      className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            </div>

            {/* Sub-Batches Grid */}
            <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
              <div className="border-b border-slate-100 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold text-slate-900 text-[15px]">Sub-Batches</h2>
                    <p className="mt-1 text-[13px] text-slate-500">
                      Add sub-batch details (one COA will be generated for the master lot)
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addSubBatch}
                    className="border-slate-200 h-9"
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Add Row
                  </Button>
                </div>
              </div>
              <div className="ag-theme-alpine" style={{ height: Math.min(300, 56 + subBatches.length * 42) }}>
                <AgGridReact<SubBatchRow>
                  rowData={subBatches}
                  columnDefs={subBatchColDefs}
                  defaultColDef={defaultColDef}
                  getRowId={(params) => params.data.id.toString()}
                  onCellValueChanged={(event) => {
                    setSubBatches(prev =>
                      prev.map(sb => sb.id === event.data.id ? event.data : sb)
                    )
                  }}
                  domLayout="autoHeight"
                  suppressRowClickSelection
                  stopEditingWhenCellsLoseFocus
                />
              </div>
            </div>
          </>
        )}

        {/* multi_sku_composite: Composite Products Grid */}
        {watchedLotType === "multi_sku_composite" && (
          <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
            <div className="border-b border-slate-100 px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900 text-[15px]">Composite Batch Details</h2>
                  <p className="mt-1 text-[13px] text-slate-500">
                    Add products with their batch numbers (a COA will be generated for each item)
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addCompositeProduct}
                  className="border-slate-200 h-9"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add Row
                </Button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    {compositeTable.getHeaderGroups().map((headerGroup) =>
                      headerGroup.headers.map((header) => (
                        <th
                          key={header.id}
                          className="text-left font-semibold text-slate-700 text-xs tracking-wide px-3 py-2 uppercase"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </th>
                      ))
                    )}
                  </tr>
                </thead>
                <tbody>
                  {compositeTable.getRowModel().rows.map((row) => (
                    <tr key={row.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-3 py-1.5">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Submit */}
        <div className="flex gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/")}
            className="border-slate-200 h-10"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={createMutation.isPending}
            className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10"
          >
            {createMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Create Sample
          </Button>
        </div>
      </form>

      {/* Product Selection Dialog */}
      <Dialog open={isProductDialogOpen} onOpenChange={setIsProductDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">Add Product</DialogTitle>
            <DialogDescription className="text-[14px] text-slate-500">
              Search and select a product to add
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            <Input
              placeholder="Search products..."
              value={productSearch}
              onChange={(e) => setProductSearch(e.target.value)}
              autoFocus
              className="border-slate-200 h-11"
            />

            <div className="max-h-[300px] overflow-y-auto space-y-1">
              {filteredProducts?.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => addProduct(product)}
                  disabled={selectedProducts.some((sp) => sp.product.id === product.id)}
                  className="w-full text-left p-3.5 rounded-xl hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors border border-transparent hover:border-slate-200"
                >
                  <p className="font-semibold text-slate-900 text-[14px]">{product.display_name}</p>
                  <p className="text-[12px] text-slate-500 mt-0.5">{product.brand}</p>
                </button>
              ))}
              {filteredProducts?.length === 0 && (
                <p className="text-center text-[14px] text-slate-500 py-6">
                  No products found
                </p>
              )}
            </div>
          </div>

          <DialogFooter className="pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsProductDialogOpen(false)}
              className="border-slate-200 h-10"
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
