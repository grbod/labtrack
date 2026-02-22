import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  labTestTypesApi,
  type LabTestTypeFilters,
  type CreateLabTestTypeData,
  type UpdateLabTestTypeData,
  type BulkImportLabTestTypeRow,
} from "@/api/labTestTypes"
import { extractApiErrorMessage } from "@/lib/api-utils"

export const labTestTypeKeys = {
  all: ["labTestTypes"] as const,
  lists: () => [...labTestTypeKeys.all, "list"] as const,
  list: (filters: LabTestTypeFilters) => [...labTestTypeKeys.lists(), filters] as const,
  details: () => [...labTestTypeKeys.all, "detail"] as const,
  detail: (id: number) => [...labTestTypeKeys.details(), id] as const,
  categories: () => [...labTestTypeKeys.all, "categories"] as const,
}

export function useLabTestTypes(filters: LabTestTypeFilters = {}) {
  return useQuery({
    queryKey: labTestTypeKeys.list(filters),
    queryFn: () => labTestTypesApi.list(filters),
  })
}

export function useLabTestType(id: number) {
  return useQuery({
    queryKey: labTestTypeKeys.detail(id),
    queryFn: () => labTestTypesApi.get(id),
    enabled: !!id,
  })
}

export function useLabTestTypeCategories() {
  return useQuery({
    queryKey: labTestTypeKeys.categories(),
    queryFn: () => labTestTypesApi.getCategories(),
  })
}

export function useCreateLabTestType() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateLabTestTypeData) => labTestTypesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: labTestTypeKeys.lists() })
      queryClient.invalidateQueries({ queryKey: labTestTypeKeys.categories() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to create lab test type"))
    },
  })
}

export function useUpdateLabTestType() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateLabTestTypeData }) =>
      labTestTypesApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: labTestTypeKeys.lists() })
      queryClient.invalidateQueries({ queryKey: labTestTypeKeys.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: labTestTypeKeys.categories() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update lab test type"))
    },
  })
}

export function useDeleteLabTestType() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => labTestTypesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: labTestTypeKeys.lists() })
      queryClient.invalidateQueries({ queryKey: labTestTypeKeys.categories() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to delete lab test type"))
    },
  })
}

export function useBulkImportLabTestTypes() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (rows: BulkImportLabTestTypeRow[]) => labTestTypesApi.bulkImport(rows),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: labTestTypeKeys.lists() })
      queryClient.invalidateQueries({ queryKey: labTestTypeKeys.categories() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to bulk import lab test types"))
    },
  })
}
