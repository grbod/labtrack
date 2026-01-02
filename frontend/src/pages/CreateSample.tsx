import { useState, useCallback, useMemo } from "react"
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

import { useProducts } from "@/hooks/useProducts"
import { useCreateLot, useLots, useCreateSublotsBulk } from "@/hooks/useLots"
import type { Product, LotType } from "@/types"

// User-selectable lot types (excludes SUBLOT which is created automatically)
type SelectableLotType = "STANDARD" | "PARENT_LOT" | "MULTI_SKU_COMPOSITE"

const LOT_TYPES: { value: SelectableLotType; label: string; description: string }[] = [
  {
    value: "STANDARD",
    label: "Standard Lot",
    description: "Single product, single lot",
  },
  {
    value: "PARENT_LOT",
    label: "Parent Lot",
    description: "Master lot with sublots",
  },
  {
    value: "MULTI_SKU_COMPOSITE",
    label: "Multi-SKU Composite",
    description: "Multiple products combined",
  },
]

const sampleSchema = z.object({
  lot_number: z.string().min(1, "Lot number is required"),
  lot_type: z.enum(["STANDARD", "PARENT_LOT", "MULTI_SKU_COMPOSITE"]),
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

  // Sub-batch state for PARENT_LOT
  const [subBatches, setSubBatches] = useState<SubBatchRow[]>([
    { id: 1, mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }
  ])
  const [nextSubBatchId, setNextSubBatchId] = useState(2)

  // Composite products state for MULTI_SKU_COMPOSITE
  const [compositeProducts, setCompositeProducts] = useState<CompositeProductRow[]>([
    { id: 1, product_id: null, product_name: '', mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }
  ])
  const [nextCompositeId, setNextCompositeId] = useState(2)
  const [editingCompositeCell, setEditingCompositeCell] = useState<{ rowId: number; columnId: string } | null>(null)

  const { data: productsData } = useProducts({ page_size: 100 })
  const { data: lotsData } = useLots({ page: 1, page_size: 10 })
  const createMutation = useCreateLot()
  const createSublotsMutation = useCreateSublotsBulk()

  const form = useForm<SampleForm>({
    resolver: zodResolver(sampleSchema),
    defaultValues: {
      lot_type: "STANDARD",
      generate_coa: true,
    },
  })

  const { register, handleSubmit, watch, setValue, formState: { errors } } = form
  const watchedLotType = watch("lot_type")

  const onSubmit = async (formData: SampleForm) => {
    try {
      if (formData.lot_type === "PARENT_LOT") {
        // For PARENT_LOT: Create lot then create sublots
        const validSubBatches = subBatches.filter(sb => sb.batch_number.trim() !== '')
        if (validSubBatches.length === 0) {
          alert("Please add at least one sub-batch")
          return
        }

        // Calculate earliest mfg date from sub-batches
        const earliestMfgDate = validSubBatches.reduce((min, sb) =>
          sb.mfg_date < min ? sb.mfg_date : min, validSubBatches[0].mfg_date)

        const lot = await createMutation.mutateAsync({
          lot_number: formData.lot_number,
          lot_type: "PARENT_LOT" as LotType,
          mfg_date: earliestMfgDate,
          exp_date: formData.exp_date || undefined,
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
      } else if (formData.lot_type === "MULTI_SKU_COMPOSITE") {
        // For MULTI_SKU_COMPOSITE: Use composite products grid data
        const validProducts = compositeProducts.filter(cp => cp.product_id !== null && cp.batch_number.trim() !== '')
        if (validProducts.length === 0) {
          alert("Please add at least one product")
          return
        }

        // Generate composite lot number from batch numbers
        const compositeLotNumber = "COMP-" + validProducts.map(p => p.batch_number).join("-")

        // Calculate equal percentages if not set
        const totalPercentage = validProducts.reduce((sum, p) => sum + (p.percentage || 0), 0)
        const equalPercentage = totalPercentage === 0 ? 100 / validProducts.length : undefined

        // Calculate earliest mfg date
        const earliestMfgDate = validProducts.reduce((min, cp) =>
          cp.mfg_date < min ? cp.mfg_date : min, validProducts[0].mfg_date)

        await createMutation.mutateAsync({
          lot_number: compositeLotNumber,
          lot_type: "MULTI_SKU_COMPOSITE" as LotType,
          mfg_date: earliestMfgDate,
          exp_date: formData.exp_date || undefined,
          reference_number: formData.reference_number || undefined,
          generate_coa: formData.generate_coa,
          products: validProducts.map((cp) => ({
            product_id: cp.product_id!,
            percentage: cp.percentage || equalPercentage,
          })),
        })

        navigate("/")
      } else {
        // STANDARD lot - use original logic
        await createMutation.mutateAsync({
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
        })
        navigate("/")
      }
    } catch {
      // Error handled by mutation
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

  const compositeColDefs = useMemo<ColDef<CompositeProductRow>[]>(() => [
    {
      field: 'product_name',
      headerName: 'Product',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: productOptions,
      },
      valueSetter: (params) => {
        const product = productsData?.items.find(p => p.display_name === params.newValue)
        if (product) {
          params.data.product_id = product.id
          params.data.product_name = product.display_name
          return true
        }
        return false
      },
      flex: 2,
    },
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
      field: 'percentage',
      headerName: '%',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: {
        min: 0,
        max: 100,
        precision: 1,
      },
      valueFormatter: (params: ValueFormatterParams) => params.value ? `${params.value}%` : '',
      width: 80,
    },
    {
      headerName: '',
      width: 60,
      cellRenderer: (params: ICellRendererParams<CompositeProductRow>) => (
        <button
          onClick={() => removeCompositeProduct(params.data?.id ?? 0)}
          className="p-1 text-slate-400 hover:text-red-600 transition-colors"
          type="button"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      ),
    },
  ], [productOptions, productsData, removeCompositeProduct])

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
                />
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
                  className="border-slate-200 h-10"
                />
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

        {/* PARENT_LOT: Sub-Batches Grid */}
        {watchedLotType === "PARENT_LOT" && (
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

        {/* MULTI_SKU_COMPOSITE: Composite Products Grid */}
        {watchedLotType === "MULTI_SKU_COMPOSITE" && (
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
            <div className="ag-theme-alpine" style={{ height: Math.min(350, 56 + compositeProducts.length * 42) }}>
              <AgGridReact<CompositeProductRow>
                rowData={compositeProducts}
                columnDefs={compositeColDefs}
                defaultColDef={defaultColDef}
                getRowId={(params) => params.data.id.toString()}
                onCellValueChanged={(event) => {
                  setCompositeProducts(prev =>
                    prev.map(cp => cp.id === event.data.id ? event.data : cp)
                  )
                }}
                domLayout="autoHeight"
                suppressRowClickSelection
                stopEditingWhenCellsLoseFocus
              />
            </div>
          </div>
        )}

        {/* STANDARD: Product Association */}
        {watchedLotType === "STANDARD" && (
          <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
            <div className="border-b border-slate-100 px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900 text-[15px]">Products</h2>
                  <p className="mt-1 text-[13px] text-slate-500">
                    Associate a product with this lot
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsProductDialogOpen(true)}
                  className="border-slate-200 h-9"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add Product
                </Button>
              </div>
            </div>
            <div className="p-6">
              {selectedProducts.length === 0 ? (
                <div className="text-center py-10">
                  <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center">
                    <Package className="h-7 w-7 text-slate-400" />
                  </div>
                  <p className="mt-4 text-[14px] font-medium text-slate-600">No products added yet</p>
                  <p className="mt-1 text-[13px] text-slate-500">Add a product to associate with this lot</p>
                  <button
                    type="button"
                    onClick={() => setIsProductDialogOpen(true)}
                    className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                  >
                    Add a product
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  {selectedProducts.map((sp) => (
                    <div
                      key={sp.product.id}
                      className="flex items-center gap-3 p-4 border border-slate-200/80 rounded-xl bg-slate-50/30 hover:bg-slate-50/50 transition-colors"
                    >
                      <div className="flex-1">
                        <p className="font-semibold text-slate-900 text-[14px]">{sp.product.display_name}</p>
                        <p className="text-[12px] text-slate-500 mt-0.5">
                          {sp.product.brand}
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeProduct(sp.product.id)}
                        className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
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
