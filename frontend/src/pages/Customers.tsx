import { useState } from "react"
import { motion } from "framer-motion"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Pencil, Trash2, Search, Loader2, Users, RotateCcw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
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
import { Badge } from "@/components/ui/badge"

import {
  useCustomers,
  useCreateCustomer,
  useUpdateCustomer,
  useDeactivateCustomer,
  useActivateCustomer,
} from "@/hooks/useCustomers"
import type { Customer } from "@/types"

const customerSchema = z.object({
  company_name: z.string().min(1, "Company name is required"),
  contact_name: z.string().min(1, "Contact name is required"),
  email: z.string().email("Valid email is required"),
})

type CustomerForm = z.infer<typeof customerSchema>

export function CustomersPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [includeInactive, setIncludeInactive] = useState(false)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null)

  const { data, isLoading } = useCustomers({
    page,
    page_size: 50,
    search: search || undefined,
    include_inactive: includeInactive,
  })

  const createMutation = useCreateCustomer()
  const updateMutation = useUpdateCustomer()
  const deactivateMutation = useDeactivateCustomer()
  const activateMutation = useActivateCustomer()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CustomerForm>({
    resolver: zodResolver(customerSchema),
  })

  const openCreateDialog = () => {
    setEditingCustomer(null)
    reset({
      company_name: "",
      contact_name: "",
      email: "",
    })
    setIsDialogOpen(true)
  }

  const openEditDialog = (customer: Customer) => {
    setEditingCustomer(customer)
    reset({
      company_name: customer.company_name,
      contact_name: customer.contact_name,
      email: customer.email,
    })
    setIsDialogOpen(true)
  }

  const onSubmit = async (formData: CustomerForm) => {
    try {
      if (editingCustomer) {
        await updateMutation.mutateAsync({ id: editingCustomer.id, data: formData })
      } else {
        await createMutation.mutateAsync(formData)
      }
      setIsDialogOpen(false)
    } catch {
      // Error handled by mutation
    }
  }

  const handleDeactivate = async (id: number) => {
    if (confirm("Are you sure you want to deactivate this customer?")) {
      await deactivateMutation.mutateAsync(id)
    }
  }

  const handleActivate = async (id: number) => {
    await activateMutation.mutateAsync(id)
  }

  const isMutating = createMutation.isPending || updateMutation.isPending

  return (
    <div className="mx-auto max-w-7xl p-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.275 }}
        className="space-y-8"
      >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Customers</h1>
          <p className="mt-1.5 text-[15px] text-slate-500">Manage COA recipients and contacts</p>
        </div>
        <Button
          onClick={openCreateDialog}
          className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10 px-4"
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Customer
        </Button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search customers..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            className="pl-10 h-11 bg-white border-slate-200 rounded-lg shadow-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300 transition-shadow"
          />
        </div>
        <label className="flex items-center gap-2 text-[14px] text-slate-600">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => {
              setIncludeInactive(e.target.checked)
              setPage(1)
            }}
            className="rounded border-slate-300 text-slate-900 focus:ring-slate-500 h-4 w-4"
          />
          Show inactive
        </label>
        <span className="text-[14px] font-medium text-slate-500">
          {data?.total ?? 0} customers
        </span>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
          </div>
        ) : data?.items.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No customers found"
            description="Get started by adding your first customer"
            actionLabel="Add your first customer"
            onAction={openCreateDialog}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100">
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Company Name</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Contact Name</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Email</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Status</TableHead>
                <TableHead className="w-[100px] font-semibold text-slate-600 text-[13px] tracking-wide">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((customer) => (
                <TableRow key={customer.id} className="hover:bg-slate-50/50 transition-colors">
                  <TableCell className="font-semibold text-slate-900 text-[14px]">
                    {customer.company_name}
                  </TableCell>
                  <TableCell className="text-slate-700 text-[14px]">
                    {customer.contact_name}
                  </TableCell>
                  <TableCell className="text-slate-500 text-[14px]">
                    {customer.email}
                  </TableCell>
                  <TableCell>
                    {customer.is_active ? (
                      <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 font-medium">
                        Active
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="bg-slate-50 text-slate-500 border-slate-200 font-medium">
                        Inactive
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-0.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditDialog(customer)}
                        className="h-8 w-8 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      {customer.is_active ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeactivate(customer.id)}
                          disabled={deactivateMutation.isPending}
                          className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Deactivate customer"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleActivate(customer.id)}
                          disabled={activateMutation.isPending}
                          className="h-8 w-8 p-0 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                          title="Reactivate customer"
                        >
                          <RotateCcw className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-5 py-4">
            <p className="text-[14px] text-slate-500">
              Page {data.page} of {data.total_pages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="border-slate-200 hover:bg-slate-50 h-9"
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page === data.total_pages}
                className="border-slate-200 hover:bg-slate-50 h-9"
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Add/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">
              {editingCustomer ? "Edit Customer" : "Add Customer"}
            </DialogTitle>
            <DialogDescription className="text-[14px] text-slate-500">
              {editingCustomer
                ? "Update customer information"
                : "Add a new customer for COA delivery"}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label htmlFor="company_name" className="text-[13px] font-semibold text-slate-700">
                Company Name *
              </Label>
              <Input
                id="company_name"
                {...register("company_name")}
                aria-invalid={!!errors.company_name}
                className="border-slate-200 h-10"
              />
              {errors.company_name && (
                <p className="text-[13px] text-red-600">{errors.company_name.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="contact_name" className="text-[13px] font-semibold text-slate-700">
                Contact Name *
              </Label>
              <Input
                id="contact_name"
                {...register("contact_name")}
                aria-invalid={!!errors.contact_name}
                className="border-slate-200 h-10"
              />
              {errors.contact_name && (
                <p className="text-[13px] text-red-600">{errors.contact_name.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-[13px] font-semibold text-slate-700">
                Email *
              </Label>
              <Input
                id="email"
                type="email"
                {...register("email")}
                aria-invalid={!!errors.email}
                className="border-slate-200 h-10"
              />
              {errors.email && (
                <p className="text-[13px] text-red-600">{errors.email.message}</p>
              )}
            </div>

            <DialogFooter className="pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
                className="border-slate-200 h-10"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isMutating}
                className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10"
              >
                {isMutating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingCustomer ? "Save Changes" : "Add Customer"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      </motion.div>
    </div>
  )
}
