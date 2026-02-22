import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  productsApi,
  type ProductFilters,
  type CreateProductData,
  type UpdateProductData,
  type CreateSizeData,
  type UpdateSizeData,
  type CreateTestSpecData,
  type UpdateTestSpecData,
  type BulkImportProductRow,
} from "@/api/products"
import { extractApiErrorMessage } from "@/lib/api-utils"

export const productKeys = {
  all: ["products"] as const,
  lists: () => [...productKeys.all, "list"] as const,
  list: (filters: ProductFilters) => [...productKeys.lists(), filters] as const,
  details: () => [...productKeys.all, "detail"] as const,
  detail: (id: number) => [...productKeys.details(), id] as const,
  brands: () => [...productKeys.all, "brands"] as const,
  sizes: (productId: number) => [...productKeys.all, "sizes", productId] as const,
  testSpecs: (productId: number) => [...productKeys.all, "testSpecs", productId] as const,
}

export function useProducts(filters: ProductFilters = {}) {
  return useQuery({
    queryKey: productKeys.list(filters),
    queryFn: () => productsApi.list(filters),
  })
}

export function useProduct(id: number) {
  return useQuery({
    queryKey: productKeys.detail(id),
    queryFn: () => productsApi.get(id),
    enabled: !!id,
  })
}

export function useBrands() {
  return useQuery({
    queryKey: productKeys.brands(),
    queryFn: () => productsApi.getBrands(),
  })
}

export function useCreateProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateProductData) => productsApi.create(data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to create product"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productKeys.brands() })
    },
  })
}

export function useUpdateProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateProductData }) =>
      productsApi.update(id, data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update product"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.id) })
    },
  })
}

export function useArchiveProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      productsApi.archive(id, { reason }),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to archive product"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: ["archivedProducts"] })
    },
  })
}

export function useRestoreProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => productsApi.restore(id),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to restore product"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: ["archivedProducts"] })
    },
  })
}

// Deprecated - use useArchiveProduct instead
export function useDeleteProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      productsApi.archive(id, { reason }),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to delete product"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
    },
  })
}

// Size hooks
export function useProductSizes(productId: number) {
  return useQuery({
    queryKey: productKeys.sizes(productId),
    queryFn: () => productsApi.listSizes(productId),
    enabled: !!productId,
  })
}

export function useCreateSize() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ productId, data }: { productId: number; data: CreateSizeData }) =>
      productsApi.createSize(productId, data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to create size"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.sizes(variables.productId) })
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.productId) })
    },
  })
}

export function useUpdateSize() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ productId, sizeId, data }: { productId: number; sizeId: number; data: UpdateSizeData }) =>
      productsApi.updateSize(productId, sizeId, data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update size"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.sizes(variables.productId) })
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.productId) })
    },
  })
}

export function useDeleteSize() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ productId, sizeId }: { productId: number; sizeId: number }) =>
      productsApi.deleteSize(productId, sizeId),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to delete size"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.sizes(variables.productId) })
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.productId) })
    },
  })
}

// Test Specification hooks
export function useProductWithSpecs(id: number) {
  return useQuery({
    queryKey: productKeys.detail(id),
    queryFn: () => productsApi.getWithSpecs(id),
    enabled: !!id,
  })
}

export function useProductTestSpecs(productId: number) {
  return useQuery({
    queryKey: productKeys.testSpecs(productId),
    queryFn: () => productsApi.listTestSpecs(productId),
    enabled: !!productId,
  })
}

export function useCreateTestSpec() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ productId, data }: { productId: number; data: CreateTestSpecData }) =>
      productsApi.createTestSpec(productId, data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to create test spec"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.testSpecs(variables.productId) })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.productId) })
    },
  })
}

export function useUpdateTestSpec() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ productId, specId, data }: { productId: number; specId: number; data: UpdateTestSpecData }) =>
      productsApi.updateTestSpec(productId, specId, data),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update test spec"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.testSpecs(variables.productId) })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.productId) })
    },
  })
}

export function useDeleteTestSpec() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ productId, specId }: { productId: number; specId: number }) =>
      productsApi.deleteTestSpec(productId, specId),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to delete test spec"))
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.testSpecs(variables.productId) })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.productId) })
    },
  })
}

export function useBulkImportProducts() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (rows: BulkImportProductRow[]) => productsApi.bulkImport(rows),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to bulk import products"))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productKeys.brands() })
    },
  })
}
