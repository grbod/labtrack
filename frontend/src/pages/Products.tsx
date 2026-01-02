import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Pencil, Trash2, Search, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import { useProducts, useCreateProduct, useUpdateProduct, useDeleteProduct } from "@/hooks/useProducts"
import type { Product } from "@/types"
import type { CreateProductData } from "@/api/products"

const productSchema = z.object({
  brand: z.string().min(1, "Brand is required"),
  product_name: z.string().min(1, "Product name is required"),
  flavor: z.string().optional(),
  size: z.string().optional(),
  display_name: z.string().min(1, "Display name is required"),
  serving_size: z.string().optional(),
  expiry_duration_months: z.number().int().positive(),
})

type ProductForm = z.infer<typeof productSchema>

export function ProductsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)

  const { data, isLoading } = useProducts({ page, page_size: 50, search: search || undefined })
  const createMutation = useCreateProduct()
  const updateMutation = useUpdateProduct()
  const deleteMutation = useDeleteProduct()

  const form = useForm<ProductForm>({
    resolver: zodResolver(productSchema),
    defaultValues: {
      expiry_duration_months: 36,
    },
  })

  const { register, handleSubmit, reset, formState: { errors } } = form

  const openCreateDialog = () => {
    setEditingProduct(null)
    reset({
      brand: "",
      product_name: "",
      flavor: "",
      size: "",
      display_name: "",
      serving_size: "",
      expiry_duration_months: 36,
    })
    setIsDialogOpen(true)
  }

  const openEditDialog = (product: Product) => {
    setEditingProduct(product)
    reset({
      brand: product.brand,
      product_name: product.product_name,
      flavor: product.flavor || "",
      size: product.size || "",
      display_name: product.display_name,
      serving_size: product.serving_size?.toString() || "",
      expiry_duration_months: product.expiry_duration_months,
    })
    setIsDialogOpen(true)
  }

  const onSubmit = async (formData: ProductForm) => {
    const servingSizeNum = formData.serving_size ? parseFloat(formData.serving_size) : undefined
    const data: CreateProductData = {
      brand: formData.brand,
      product_name: formData.product_name,
      display_name: formData.display_name,
      flavor: formData.flavor || undefined,
      size: formData.size || undefined,
      serving_size: servingSizeNum && !isNaN(servingSizeNum) ? servingSizeNum : undefined,
      expiry_duration_months: formData.expiry_duration_months,
    }

    try {
      if (editingProduct) {
        await updateMutation.mutateAsync({ id: editingProduct.id, data })
      } else {
        await createMutation.mutateAsync(data)
      }
      setIsDialogOpen(false)
    } catch {
      // Error handled by mutation
    }
  }

  const handleDelete = async (id: number) => {
    if (confirm("Are you sure you want to delete this product?")) {
      await deleteMutation.mutateAsync(id)
    }
  }

  const isMutating = createMutation.isPending || updateMutation.isPending

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Products</h1>
          <p className="text-muted-foreground text-sm">Manage your product catalog</p>
        </div>
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Add Product
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search products..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setPage(1)
                }}
                className="pl-8"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            {data?.total ?? 0} Products
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Brand</TableHead>
                  <TableHead>Product Name</TableHead>
                  <TableHead>Flavor</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Serving</TableHead>
                  <TableHead>Expiry</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((product) => (
                  <TableRow key={product.id}>
                    <TableCell className="font-medium">{product.brand}</TableCell>
                    <TableCell>{product.product_name}</TableCell>
                    <TableCell className="text-muted-foreground">{product.flavor || "-"}</TableCell>
                    <TableCell className="text-muted-foreground">{product.size || "-"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {product.serving_size ? `${product.serving_size}g` : "-"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {product.expiry_duration_months}mo
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => openEditDialog(product)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => handleDelete(product.id)}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {data?.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      No products found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {data && data.total_pages > 1 && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-muted-foreground">
                Page {data.page} of {data.total_pages}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={page === data.total_pages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingProduct ? "Edit Product" : "Add Product"}
            </DialogTitle>
            <DialogDescription>
              {editingProduct
                ? "Update product information"
                : "Add a new product to the catalog"}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="brand">Brand *</Label>
                <Input
                  id="brand"
                  {...register("brand")}
                  aria-invalid={!!errors.brand}
                />
                {errors.brand && (
                  <p className="text-sm text-destructive">{errors.brand.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="product_name">Product Name *</Label>
                <Input
                  id="product_name"
                  {...register("product_name")}
                  aria-invalid={!!errors.product_name}
                />
                {errors.product_name && (
                  <p className="text-sm text-destructive">{errors.product_name.message}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="flavor">Flavor</Label>
                <Input id="flavor" {...register("flavor")} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="size">Size</Label>
                <Input id="size" {...register("size")} placeholder="e.g., 2.5 lbs" />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="display_name">Display Name *</Label>
              <Input
                id="display_name"
                {...register("display_name")}
                aria-invalid={!!errors.display_name}
              />
              {errors.display_name && (
                <p className="text-sm text-destructive">{errors.display_name.message}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="serving_size">Serving Size (g)</Label>
                <Input
                  id="serving_size"
                  type="number"
                  step="0.01"
                  {...register("serving_size")}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="expiry_duration_months">Expiry (months)</Label>
                <Input
                  id="expiry_duration_months"
                  type="number"
                  {...register("expiry_duration_months")}
                />
              </div>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isMutating}>
                {isMutating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingProduct ? "Save Changes" : "Add Product"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
